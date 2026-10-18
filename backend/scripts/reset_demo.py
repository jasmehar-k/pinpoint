"""Restore demo state between rehearsals:
- delete DMs and #help replies Pinpoint posted to Slack (the bot can delete its own messages)
- clear pending actions, meetings booked through Pinpoint, corrections, promoted answers
- regenerate this week's calendars

Restart the API afterwards: open conversations live in its memory.

    uv run python -m scripts.reset_demo [--keep-slack]
"""

import argparse
import os

import db
from scripts import gen_meetings


def delete_slack_messages(conn) -> int:
    """Pinpoint's DMs (from approved actions) and its #help replies."""
    dms = conn.execute(
        "select result->>'channel', result->>'ts' from pending_actions "
        "where kind = 'send_message' and result->>'delivery' = 'slack'"
    ).fetchall()
    replies = conn.execute("select channel_id, reply_ts from slack_replies where reply_ts is not null").fetchall()
    rows = dms + replies
    if not rows or not os.getenv("SLACK_BOT_TOKEN"):
        return 0
    from slack_sdk.errors import SlackApiError

    from connectors.slack import client

    web, deleted = client(), 0
    for channel, ts in rows:
        try:
            web.chat_delete(channel=channel, ts=ts)
            deleted += 1
        except SlackApiError as e:  # already deleted by hand, etc.
            print(f"  couldn't delete {ts}: {e.response.get('error')}")
    return deleted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep-slack", action="store_true", help="leave sent DMs and #help replies in Slack")
    args = parser.parse_args()

    with db.connect(vector=False) as conn:
        deleted = 0 if args.keep_slack else delete_slack_messages(conn)
        counts = {
            "pending actions": conn.execute("delete from pending_actions").rowcount,
            "booked meetings": conn.execute("delete from meetings where not seeded").rowcount,
            "corrections": conn.execute("delete from corrections").rowcount,
            "promoted answers": conn.execute("delete from artifacts where kind = 'answer'").rowcount,
            "#help replies": conn.execute("delete from slack_replies").rowcount,
        }
    print(f"deleted {deleted} Slack messages, " + ", ".join(f"{n} {k}" for k, n in counts.items()))
    gen_meetings.main()
    print("restart the API to clear open conversations")


if __name__ == "__main__":
    main()
