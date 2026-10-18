"""Ingest ~6 months of merged twentyhq/twenty PRs. Rerunnable; raw pages are cached.

    uv run python -m scripts.ingest_github [--days 182] [--refresh]
"""

import argparse
from collections import Counter
from datetime import date, timedelta

import db
from connectors import github
from connectors.store import store


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=182)
    parser.add_argument("--refresh", action="store_true", help="ignore the raw cache")
    args = parser.parse_args()

    until = date.today()
    since = until - timedelta(days=args.days)
    print(f"fetching merged PRs {since}..{until}")

    artifacts, events, skipped = {}, [], 0
    for pr in github.fetch(since, until, refresh=args.refresh):
        artifact, pr_events = github.normalize_pr(pr)
        if artifact is None:
            skipped += 1
            continue
        artifacts[artifact.id] = artifact
        events.extend(pr_events)

    with db.connect(vector=False) as conn:
        store(conn, list(artifacts.values()), events)

    by_type = Counter(e.type for e in events)
    print(f"stored {len(artifacts)} PRs ({skipped} outside ingested packages), events {dict(by_type)}")


if __name__ == "__main__":
    main()
