"""Slack connector: threads in public channels the bot is a member of -> Artifacts + Events.

fetch_threads() caches raw messages under backend/data/raw/slack/, one file per channel and
day window, so reruns are free (pass refresh=True to pick up new messages).
normalize_thread() is pure and does the mapping.
"""

import html
import json
import os
import re
import time
from collections.abc import Callable
from datetime import UTC, datetime

from slack_sdk import WebClient
from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler

import config
from schema import Artifact, Event, Person

CACHE_DIR = config.BACKEND_ROOT / "data" / "raw" / "slack"
TITLE_CHARS = 80
PAGE_SIZE = 200


# ---- fetch (network) ----

def client() -> WebClient:
    token = os.getenv("SLACK_BOT_TOKEN")
    if not token:
        raise RuntimeError("SLACK_BOT_TOKEN is not set. See docs/slack-setup.md.")
    web = WebClient(token=token)
    # Sleeps for Retry-After and retries on HTTP 429
    web.retry_handlers.append(RateLimitErrorRetryHandler(max_retry_count=5))
    return web


def paginate(call: Callable, key: str, **kwargs) -> list[dict]:
    """Collect `key` across every page of a cursor-paginated Slack method."""
    items, cursor = [], None
    while True:
        params = {**kwargs, "limit": PAGE_SIZE}
        if cursor:
            params["cursor"] = cursor
        res = call(**params)
        items.extend(res.get(key) or [])
        cursor = (res.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            return items


def workspace_url(web: WebClient) -> str:
    """e.g. https://acme.slack.com/ (always with a trailing slash)."""
    return web.auth_test()["url"].rstrip("/") + "/"


def readable_channels(web: WebClient, names: list[str] | None = None) -> tuple[list[dict], list[str]]:
    """Public channels the bot can read, plus names of channels it can't (not a member).
    `names` limits the result to those channels (leading # optional)."""
    channels = paginate(web.conversations_list, "channels",
                        types="public_channel", exclude_archived=True)
    wanted = {n.lstrip("#") for n in names} if names else None
    if wanted:
        missing = wanted - {c["name"] for c in channels}
        for name in sorted(missing):
            print(f"  no public channel named #{name}")
        channels = [c for c in channels if c["name"] in wanted]
    readable = [c for c in channels if c.get("is_member")]
    skipped = sorted(c["name"] for c in channels if not c.get("is_member"))
    return readable, skipped


def _fetch_channel(web: WebClient, channel_id: str, oldest: float) -> list[list[dict]]:
    history = paginate(web.conversations_history, "messages", channel=channel_id, oldest=str(oldest))
    threads = []
    for msg in history:
        if msg.get("reply_count"):
            threads.append(paginate(web.conversations_replies, "messages",
                                    channel=channel_id, ts=msg["ts"]))
        else:
            threads.append([msg])
    return threads


def fetch_threads(web: WebClient, channel: dict, days: int, refresh: bool = False) -> list[list[dict]]:
    """Raw threads (each a list of messages, root first) from the last `days` days."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{channel['id']}_{days}d.json"
    if path.exists() and not refresh:
        cached = json.loads(path.read_text())
        print(f"  #{channel['name']}: using cache from {cached['fetched_at']} (--refresh to refetch)")
        return cached["threads"]
    threads = _fetch_channel(web, channel["id"], time.time() - days * 86400)
    path.write_text(json.dumps({"fetched_at": datetime.now(UTC).isoformat(), "threads": threads}))
    print(f"  #{channel['name']}: fetched {len(threads)} threads")
    return threads


# ---- normalize (pure) ----

def permalink(workspace: str, channel_id: str, ts: str) -> str:
    return f"{workspace.rstrip('/')}/archives/{channel_id}/p{ts.replace('.', '')}"


def _ts(ts: str) -> datetime:
    return datetime.fromtimestamp(float(ts), tz=UTC)


def _is_human(msg: dict) -> bool:
    return not msg.get("subtype") and not msg.get("bot_id") and bool(msg.get("user"))


def clean_text(text: str, people: dict[str, Person]) -> str:
    """Slack markup -> plain text: <@U1> -> @Name, <#C1|help> -> #help, <url|label> -> label."""
    def user(m):
        p = people.get(m.group(1))
        return f"@{p.name}" if p else "@someone"

    text = re.sub(r"<@([A-Z0-9]+)(?:\|[^>]*)?>", user, text)
    text = re.sub(r"<#[A-Z0-9]+\|([^>]*)>", r"#\1", text)
    text = re.sub(r"<!(here|channel|everyone)>", r"@\1", text)
    text = re.sub(r"<([^|>]+)\|([^>]+)>", r"\2", text)
    text = re.sub(r"<([^>]+)>", r"\1", text)
    return html.unescape(text).strip()


def _title(channel_name: str, text: str) -> str:
    first = " ".join(text.split())
    if len(first) > TITLE_CHARS:
        first = first[:TITLE_CHARS].rstrip() + "..."
    return f"#{channel_name}: {first}"


def normalize_thread(
    channel: dict, messages: list[dict], people: dict[str, Person], workspace: str,
) -> tuple[Artifact | None, list[Event]]:
    """Map one raw thread to an artifact and its events. The root poster asked; every other
    person who replied answered. Returns (None, []) when nothing human is left."""
    if not messages:
        return None, []
    thread_ts = messages[0].get("thread_ts") or messages[0]["ts"]

    seen, kept = set(), []
    for msg in sorted(messages, key=lambda m: float(m["ts"])):
        if msg["ts"] in seen or not _is_human(msg):
            continue
        seen.add(msg["ts"])
        if text := clean_text(msg.get("text") or "", people):
            kept.append((msg, text))
    if not kept:
        return None, []

    def name(user_id):
        p = people.get(user_id)
        return p.name if p else "Someone"

    root, root_text = kept[0]
    artifact_id = f"slack:{channel['id']}:{thread_ts}"
    url = permalink(workspace, channel["id"], thread_ts)
    text = "\n".join(f"{name(m['user'])}: {t}" for m, t in kept)
    artifact = Artifact(
        id=artifact_id, source="slack", kind="thread", title=_title(channel["name"], root_text),
        text=text, url=url, timestamp=_ts(root["ts"]),
    )

    def event(type_, person, ts):
        return Event(source="slack", type=type_, person_id=person.id, artifact_id=artifact_id,
                     text=text, paths=[], timestamp=_ts(ts), url=url, title=artifact.title)

    events = []
    asker = root["user"]
    if p := people.get(asker):
        events.append(event("asked", p, root["ts"]))
    answered = set()
    for msg, _ in kept[1:]:
        user = msg["user"]
        if user == asker or user in answered:
            continue
        answered.add(user)
        if p := people.get(user):
            events.append(event("answered", p, msg["ts"]))

    return artifact, events
