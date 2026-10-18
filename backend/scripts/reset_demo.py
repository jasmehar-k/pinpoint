"""Restore demo state between rehearsals:
- delete DMs Pinpoint posted to Slack (the bot can delete its own messages)
- clear pending actions, meetings booked through Pinpoint, corrections, promoted answers
- regenerate this week's calendars

Restart the API afterwards: open conversations live in its memory.

    uv run python -m scripts.reset_demo [--keep-slack]
"""

import argparse
import os

import db
from scripts import gen_meetings


def delete_slack_dms(conn) -> int:
    rows = conn.execute(
        "select result from pending_actions where kind = 'send_message' and result->>'delivery' = 'slack'"
    ).fetchall()
    if not rows or not os.getenv("SLACK_BOT_TOKEN"):
        return 0
    from slack_sdk.errors import SlackApiError

    from connectors.slack import client

    web, deleted = client(), 0
    for (result,) in rows:
        try:
            web.chat_delete(channel=result["channel"], ts=result["ts"])
            deleted += 1
        except SlackApiError as e:  # already deleted by hand, etc.
            print(f"  couldn't delete {result['ts']}: {e.response.get('error')}")
    return deleted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep-slack", action="store_true", help="leave sent DMs in Slack")
    args = parser.parse_args()

    with db.connect(vector=False) as conn:
        deleted = 0 if args.keep_slack else delete_slack_dms(conn)
        counts = {
            "pending actions": conn.execute("delete from pending_actions").rowcount,
            "booked meetings": conn.execute("delete from meetings where not seeded").rowcount,
            "corrections": conn.execute("delete from corrections").rowcount,
            "promoted answers": conn.execute("delete from artifacts where kind = 'answer'").rowcount,
        }
    print(f"deleted {deleted} Slack DMs, " + ", ".join(f"{n} {k}" for k, n in counts.items()))
    gen_meetings.main()
    print("restart the API to clear open conversations")


if __name__ == "__main__":
    main()
