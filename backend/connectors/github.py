"""GitHub connector: merged PRs of twentyhq/twenty -> Artifacts + Events.

fetch() caches raw GraphQL pages under backend/data/raw/github/, one file per week,
so reruns are free. normalize_pr() is pure and does the mapping.
"""

import json
import os
import time
from collections.abc import Iterator
from datetime import date, datetime, timedelta

import httpx

import config
from org import people_by_github_login
from schema import Artifact, Event

REPO = "twentyhq/twenty"
PACKAGES = ("packages/twenty-server/", "packages/twenty-front/")
CACHE_DIR = config.BACKEND_ROOT / "data" / "raw" / "github"
BODY_CHARS = 2000

QUERY = """
query($q: String!, $after: String) {
  rateLimit { remaining resetAt }
  search(query: $q, type: ISSUE, first: 50, after: $after) {
    issueCount
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on PullRequest {
        number title body url mergedAt
        author { login }
        reviews(first: 30) { nodes { author { login } submittedAt } }
        files(first: 100) { nodes { path } }
      }
    }
  }
}
"""


def _post(q: str, after: str | None) -> dict:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is not set.")
    for attempt in range(4):
        res = httpx.post(
            "https://api.github.com/graphql",
            json={"query": QUERY, "variables": {"q": q, "after": after}},
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        )
        if res.status_code in (502, 503, 504):
            time.sleep(2 ** attempt)
            continue
        res.raise_for_status()
        body = res.json()
        if "errors" in body:
            raise RuntimeError(body["errors"])
        return body["data"]
    res.raise_for_status()
    raise RuntimeError("GitHub GraphQL kept failing")


def _fetch_week(start: date, end: date) -> list[dict]:
    q = f"repo:{REPO} is:pr is:merged merged:{start.isoformat()}..{end.isoformat()}"
    prs, after = [], None
    while True:
        data = _post(q, after)
        search = data["search"]
        if search["issueCount"] > 1000:
            raise RuntimeError(f"{q} has {search['issueCount']} results; use smaller windows")
        prs.extend(n for n in search["nodes"] if n)
        if not search["pageInfo"]["hasNextPage"]:
            return prs
        after = search["pageInfo"]["endCursor"]


def fetch(since: date, until: date, refresh: bool = False) -> Iterator[dict]:
    """Yield raw PR dicts, week by week, using the cache when present.
    The current (incomplete) week is always refetched."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    start = since
    while start <= until:
        end = min(start + timedelta(days=6), until)
        path = CACHE_DIR / f"{start.isoformat()}_{end.isoformat()}.json"
        if path.exists() and not refresh and end < until:
            prs = json.loads(path.read_text())
        else:
            prs = _fetch_week(start, end)
            path.write_text(json.dumps(prs))
            print(f"  fetched {start}..{end}: {len(prs)} PRs")
        yield from prs
        start = end + timedelta(days=1)


def _parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def normalize_pr(pr: dict, people: dict | None = None) -> tuple[Artifact | None, list[Event]]:
    """Map one raw PR to an artifact and its events. Returns (None, []) for PRs
    outside the ingested packages."""
    people = people_by_github_login() if people is None else people
    paths = [f["path"] for f in (pr.get("files") or {}).get("nodes", [])]
    if not any(p.startswith(PACKAGES) for p in paths):
        return None, []

    artifact_id = f"github:pr:{pr['number']}"
    body = (pr.get("body") or "").strip()[:BODY_CHARS]
    text = f"{pr['title']}\n\n{body}".strip()
    merged_at = _parse_ts(pr["mergedAt"])
    artifact = Artifact(
        id=artifact_id, source="github", kind="pr", title=f"{pr['title']} (#{pr['number']})",
        text=text, url=pr["url"], timestamp=merged_at, paths=paths,
    )

    def event(type_, person, ts):
        return Event(source="github", type=type_, person_id=person.id, artifact_id=artifact_id,
                     text=text, paths=paths, timestamp=ts, url=pr["url"], title=artifact.title)

    events = []
    author_login = ((pr.get("author") or {}).get("login") or "").lower()
    if author := people.get(author_login):
        events.append(event("authored", author, merged_at))

    first_review: dict[str, datetime] = {}
    for review in (pr.get("reviews") or {}).get("nodes", []):
        login = ((review.get("author") or {}).get("login") or "").lower()
        if not login or login == author_login or not review.get("submittedAt"):
            continue
        ts = _parse_ts(review["submittedAt"])
        if login not in first_review or ts < first_review[login]:
            first_review[login] = ts
    for login, ts in first_review.items():
        if reviewer := people.get(login):
            events.append(event("reviewed", reviewer, ts))

    return artifact, events
