"""Ingest threads from public Slack channels the Pinpoint bot is a member of.
Rerunnable; raw messages are cached per channel, LLM topic tags are batched.

    uv run python -m scripts.ingest_slack [--days 90] [--channel help ...] [--no-tag] [--refresh]
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
from tagging import tag_topics

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
    parser.add_argument("--refresh", action="store_true", help="ignore the raw cache")
    args = parser.parse_args()

    if not args.no_tag:
        llm.client(), llm.model()  # fail now, not after fetching, if the LLM isn't configured

    try:
        web = slack.client()
        workspace = slack.workspace_url(web)
        channels, not_member = slack.readable_channels(web, args.channel)
        print(f"reading {len(channels)} channels from {workspace}, last {args.days} days")
        raw = [(c, t) for c in channels for t in slack.fetch_threads(web, c, args.days, args.refresh)]
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

    tagged = 0
    if artifacts and not args.no_tag:
        print(f"tagging {len(artifacts)} threads")
        for artifact_id, topics in tag_topics(list(artifacts.values())).items():
            artifacts[artifact_id].topics = topics
            tagged += bool(topics)

    with db.connect(vector=False) as conn:
        store(conn, list(artifacts.values()), events)

    by_type = Counter(e.type for e in events)
    print(f"stored {len(artifacts)} threads ({tagged} with topics), events {dict(by_type)}")
    if not_member:
        names = ", ".join(f"#{n}" for n in not_member)
        print(f"skipped {len(not_member)} channels the bot isn't in: {names}. "
              "Run /invite @Pinpoint there to include them.")


if __name__ == "__main__":
    main()
