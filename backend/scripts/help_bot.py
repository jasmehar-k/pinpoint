"""Watch #help and answer new questions in-thread. Posts only when PINPOINT_MODE=live; otherwise
prints what it would post (dry run). Starts from "now" so it never answers old messages, and
records every answer in slack_replies so a restart never replies twice.

    uv run python -m scripts.help_bot [--channel help] [--once] [--every 30]
"""

import argparse
import os
import time
from datetime import UTC, datetime

import config
import db
from agent.chat import answer_question
from agent.help_bot import GUEST, format_reply, is_new_question
from connectors import slack
from org import people_by_slack_user_id

APP_URL = os.getenv("PINPOINT_APP_URL", "http://localhost:3000")


def _channel_id(web, name: str) -> str:
    channels, _ = slack.readable_channels(web, [name])
    if not channels:
        raise SystemExit(f"the bot can't read #{name}; run /invite @Pinpoint there")
    return channels[0]["id"]


def _answered(conn, channel: str, ts: str) -> bool:
    return conn.execute("select 1 from slack_replies where channel_id = %s and message_ts = %s",
                        (channel, ts)).fetchone() is not None


def poll(web, conn, channel: str, bot_user: str, oldest: float, live: bool, seen: set[str]) -> float:
    """Answer new questions since `oldest`. Returns the newest message time seen."""
    res = web.conversations_history(channel=channel, oldest=slack.slack_ts(oldest), limit=50)
    newest = oldest
    for msg in sorted(res["messages"], key=lambda m: float(m["ts"])):
        newest = max(newest, float(msg["ts"]))
        if not is_new_question(msg, bot_user) or msg["ts"] in seen or _answered(conn, channel, msg["ts"]):
            continue
        seen.add(msg["ts"])
        people = people_by_slack_user_id()
        asker = people.get(msg["user"], GUEST)
        question = slack.clean_text(msg["text"], people)
        print(f"question from {asker.name}: {question[:80]}")
        own_thread = (f"slack:{channel}:{msg['ts']}",)  # if already ingested, don't cite it
        answered = answer_question(conn, question, asker, datetime.now(UTC), exclude=own_thread)
        reply = format_reply(answered, APP_URL)
        if not live:
            print("  [dry run] would reply:\n" + "\n".join("    " + line for line in reply.splitlines()))
            continue
        posted = web.chat_postMessage(channel=channel, thread_ts=msg["ts"], text=reply,
                                      unfurl_links=False, unfurl_media=False)
        conn.execute("insert into slack_replies (channel_id, message_ts, reply_ts) values (%s, %s, %s) "
                     "on conflict do nothing", (channel, msg["ts"], posted["ts"]))
        conn.commit()
        print(f"  replied in thread ({posted['ts']})")
    return newest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", default="help")
    parser.add_argument("--every", type=float, default=30, help="seconds between polls")
    parser.add_argument("--once", action="store_true", help="poll once and exit")
    parser.add_argument("--since-minutes", type=float, default=0,
                        help="also answer questions from the last N minutes (default: only new ones)")
    args = parser.parse_args()

    live = config.MODE == "live"
    web = slack.client()
    bot_user = web.auth_test()["user_id"]
    channel = _channel_id(web, args.channel)
    oldest = time.time() - args.since_minutes * 60
    print(f"watching #{args.channel} every {args.every:.0f}s ({'LIVE: posting replies' if live else 'dry run'})")
    seen: set[str] = set()
    while True:
        with db.connect() as conn:
            oldest = poll(web, conn, channel, bot_user, oldest, live, seen)
        if args.once:
            return
        time.sleep(args.every)


if __name__ == "__main__":
    main()
