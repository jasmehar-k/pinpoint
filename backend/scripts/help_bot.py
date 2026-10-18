"""Watch #help and answer new questions in-thread. Posts only when PINPOINT_MODE=live; otherwise
prints what it would post (dry run). Starts from "now" so it never answers old messages, and
records every answer in slack_replies so a restart never replies twice.

"That answered it": when a person reacts with a check mark on one of our replies (last 2 days),
the thread is saved as a known answer (an `answer` artifact, embedded right away) so the next
person who asks something similar gets it cited.

    uv run python -m scripts.help_bot [--channel help] [--once] [--every 30]
"""

import argparse
import os
import time
from datetime import UTC, datetime

import config
import db
from agent.chat import answer_question
from agent.help_bot import GUEST, SAVED_NOTE, answered_it, format_reply, is_new_question, thread_text
from connectors import slack
from connectors.store import store
from embeddings import embed_documents
from org import people_by_slack_user_id
from schema import Artifact

APP_URL = os.getenv("PINPOINT_APP_URL", "http://localhost:3000")


def _channel_id(web, name: str) -> str:
    channels, _ = slack.readable_channels(web, [name])
    if not channels:
        raise SystemExit(f"the bot can't read #{name}; run /invite @Pinpoint there")
    return channels[0]["id"]


def _claim(conn, channel: str, ts: str) -> bool:
    """Record that we're answering this message. False if another run already did, so two bots
    running at once can't both reply."""
    row = conn.execute("insert into slack_replies (channel_id, message_ts) values (%s, %s) "
                       "on conflict do nothing returning message_ts", (channel, ts)).fetchone()
    conn.commit()
    return row is not None


def poll(web, conn, channel: str, bot_user: str, oldest: float, live: bool, seen: set[str]) -> float:
    """Answer new questions since `oldest`. Returns the newest message time seen."""
    res = web.conversations_history(channel=channel, oldest=slack.slack_ts(oldest), limit=50)
    newest = oldest
    for msg in sorted(res["messages"], key=lambda m: float(m["ts"])):
        newest = max(newest, float(msg["ts"]))
        if not is_new_question(msg, bot_user) or msg["ts"] in seen:
            continue
        seen.add(msg["ts"])
        if live and not _claim(conn, channel, msg["ts"]):
            continue
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
        try:
            posted = web.chat_postMessage(channel=channel, thread_ts=msg["ts"], text=reply,
                                          unfurl_links=False, unfurl_media=False)
        except Exception as e:  # release the claim so the next poll retries
            conn.execute("delete from slack_replies where channel_id = %s and message_ts = %s", (channel, msg["ts"]))
            conn.commit()
            seen.discard(msg["ts"])
            print(f"  couldn't reply: {e}")
            continue
        topic = answered.experts[0].topic if answered.experts else None
        conn.execute("update slack_replies set reply_ts = %s, topic = %s where channel_id = %s and message_ts = %s",
                     (posted["ts"], topic, channel, msg["ts"]))
        conn.commit()
        print(f"  replied in thread ({posted['ts']})")
    return newest


def save_answered(web, conn, channel: str, bot_user: str, workspace: str) -> None:
    """Save threads where someone reacted with a check mark on our reply."""
    rows = conn.execute(
        """
        select message_ts, reply_ts, topic from slack_replies
        where channel_id = %s and reply_ts is not null and promoted_at is null
          and created_at > now() - interval '2 days'
        """,
        (channel,),
    ).fetchall()
    for message_ts, reply_ts, topic in rows:
        thread = web.conversations_replies(channel=channel, ts=message_ts)["messages"]
        ours = next((m for m in thread if m["ts"] == reply_ts), None)
        if not ours or not answered_it(ours, bot_user):
            continue
        people = people_by_slack_user_id()
        text = thread_text(thread, people, bot_user, slack.clean_text)
        question = slack.clean_text(thread[0].get("text") or "", people)
        artifact = Artifact(
            id=f"answer:{channel}:{message_ts}", source="slack", kind="answer",
            title=f"#help (answered): {' '.join(question.split())[:80]}", text=text,
            url=slack.permalink(workspace, channel, message_ts),
            timestamp=datetime.fromtimestamp(float(message_ts), tz=UTC), topics=[topic] if topic else [],
        )
        # No events: expertise comes from the people in the thread via ingest_slack, not from this copy
        store(conn, [artifact], [])
        conn.execute("update artifacts set embedding = %s where id = %s", (embed_documents([text])[0], artifact.id))
        note = web.chat_postMessage(channel=channel, thread_ts=message_ts, text=SAVED_NOTE)
        conn.execute("update slack_replies set promoted_at = now(), confirm_ts = %s "
                     "where channel_id = %s and message_ts = %s", (note["ts"], channel, message_ts))
        conn.commit()
        print(f"  saved {artifact.id} as a known answer")


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
    workspace = slack.workspace_url(web)
    oldest = time.time() - args.since_minutes * 60
    print(f"watching #{args.channel} every {args.every:.0f}s ({'LIVE: posting replies' if live else 'dry run'})")
    seen: set[str] = set()
    while True:
        with db.connect() as conn:
            oldest = poll(web, conn, channel, bot_user, oldest, live, seen)
            if live:
                save_answered(web, conn, channel, bot_user, workspace)
        if args.once:
            return
        time.sleep(args.every)


if __name__ == "__main__":
    main()
