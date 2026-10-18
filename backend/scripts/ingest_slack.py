"""Ingest threads from public Slack channels the Pinpoint bot is a member of.
Rerunnable: refetches by default, reuses topics for unchanged threads, batches LLM tagging.
Run scripts.embed afterwards so new threads are searchable.

    uv run python -m scripts.ingest_slack [--days 90] [--channel help ...] [--no-tag] [--cached]
"""

import argparse
import sys
from collections import Counter

from slack_sdk.errors import SlackApiError

import db
import llm
from connectors import slack
from connectors.store import store
from org import people_by_slack_user_id
from tagging import reuse_tags, tag_topics


def _existing_tags(conn, ids: list[str]) -> dict[str, tuple[str, list[str]]]:
    rows = conn.execute(
        """
        select a.id, a.text, coalesce(array_agg(t.topic_id) filter (where t.topic_id is not null), '{}')
        from artifacts a left join artifact_topics t on t.artifact_id = a.id
        where a.id = any(%s) group by a.id
        """,
        (ids,),
    ).fetchall()
    return {id_: (text, list(topics)) for id_, text, topics in rows}


HINTS = {
    "invalid_auth": "SLACK_BOT_TOKEN is wrong or revoked; copy the xoxb- token again",
    "not_authed": "SLACK_BOT_TOKEN is empty",
    "missing_scope": "add the missing bot scope in the Slack app, then reinstall it",
    "not_in_channel": "run /invite @Pinpoint in that channel",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--channel", nargs="+", action="extend", default=[],
                        help="only these channels, e.g. --channel help integrations")
    parser.add_argument("--no-tag", action="store_true", help="skip LLM topic tagging")
    parser.add_argument("--cached", action="store_true",
                        help="reuse the last fetched copy instead of calling Slack (offline)")
    args = parser.parse_args()

    if not args.no_tag:
        llm.client(), llm.model()  # fail now, not after fetching, if the LLM isn't configured

    try:
        web = slack.client()
        workspace = slack.workspace_url(web)
        channels, not_member = slack.readable_channels(web, args.channel)
        print(f"reading {len(channels)} channels from {workspace}, last {args.days} days")
        raw = [(c, t) for c in channels for t in slack.fetch_threads(web, c, args.days, args.cached)]
    except SlackApiError as e:
        code = e.response.get("error", "unknown")
        sys.exit(f"Slack error: {code}. {HINTS.get(code, 'see docs/slack-setup.md')}")

    people = people_by_slack_user_id()
    artifacts, events = {}, []
    for channel, messages in raw:
        artifact, thread_events = slack.normalize_thread(channel, messages, people, workspace)
        if artifact:
            artifacts[artifact.id] = artifact
            events.extend(thread_events)

    with db.connect(vector=False) as conn:
        reused, todo = reuse_tags(list(artifacts.values()), _existing_tags(conn, list(artifacts)))
        new_tags = {}
        if todo and not args.no_tag:
            print(f"tagging {len(todo)} new or changed threads ({len(reused)} reused)")
            new_tags = tag_topics(todo)
        for artifact_id, topics in {**reused, **new_tags}.items():
            artifacts[artifact_id].topics = topics
        store(conn, list(artifacts.values()), events)

    tagged = sum(bool(a.topics) for a in artifacts.values())
    by_type = Counter(e.type for e in events)
    print(f"stored {len(artifacts)} threads ({tagged} with topics), events {dict(by_type)}")
    print("next: uv run python -m scripts.embed")
    if not_member:
        names = ", ".join(f"#{n}" for n in not_member)
        print(f"skipped {len(not_member)} channels the bot isn't in: {names}. "
              "Run /invite @Pinpoint there to include them.")


if __name__ == "__main__":
    main()
