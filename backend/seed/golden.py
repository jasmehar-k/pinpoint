"""Hand-written threads the demo depends on. Facts come straight from the real PR bodies.

seed-thread-0042 is cited by the fixtures (Dana explaining how inbound sync is triggered).
"""

from datetime import UTC, datetime, timedelta

from schema import Artifact, Event, Person
from seed import threads
from seed.threads import records_from_messages

# id, channel, topics, days ago, [(person, minutes after start, text)]
GOLDEN = [
    ("seed-thread-0042", "help", ["messaging"], 16, [
        ("aisha-bello", 0, "how does inbound Gmail sync get triggered? trying to figure out why a test mailbox took a few minutes to show new emails"),
        ("dana-okafor", 22, "When Gmail or Microsoft pings our webhook, we enqueue one job that runs the list fetch for that channel right away. That's #26180. Before it, the webhook just flipped the channel to PENDING and waited up to 5 minutes for the cron, which is probably what you saw on an older build. Bursts of pings fold into one job through BullMQ dedup, so you don't get a pile of duplicate syncs. Deltas over 50 items are still left to the import cron."),
        ("marcus-lee", 41, "The cron is the fallback for anything webhooks miss. Since #26181 each sync cron runs one cross-workspace query per tick instead of one per workspace, so it's cheap. If a channel looks stuck, check whether it's still waiting on the cron."),
        ("aisha-bello", 47, "perfect, that explains it. thanks both"),
    ]),
    ("seed-thread-0077", "help", ["messaging"], 9, [
        ("tomas-rivera", 0, "A customer's Outlook mailbox keeps doing a full resync every few hours. Any idea why?"),
        ("marcus-lee", 35, "Probably one message 404ing inside a Graph $batch. That used to fail the whole import batch as NOT_FOUND, wipe every folder cursor, and send the mailbox into an endless full resync. #26107 drops missing (404/410) messages the way Gmail already did, so check they're on a build with that."),
    ]),
    ("seed-thread-0118", "help", ["messaging"], 5, [
        ("hannah-brooks", 0, "Seeing duplicate sent emails in Gmail threads after someone replies. Known issue?"),
        ("dana-okafor", 18, "Yep, fixed in #27688. Gmail replaces the Message-ID of emails sent through its API, so when a reply made sync fetch the whole thread, the sent email didn't match its saved row and got saved twice. The save step now also matches on the Gmail message id."),
    ]),
    ("seed-thread-0163", "help", ["calendar", "messaging"], 30, [
        ("zoe-adams", 0, "Calendar import is failing with an idle-in-transaction timeout, and the error we actually get is about a failed rollback. What's going on?"),
        ("marcus-lee", 26, "That's #24681. Imports used to do their reads and planning inside the transaction, so Postgres killed the session for sitting idle in it, and the failed rollback hid the real error. Now reads happen before the transaction opens and it only holds the writes. Transient Postgres errors get retried too, instead of failing the channel."),
    ]),
    ("seed-thread-0201", "deploys", ["deploys"], 12, [
        ("leo-costa", 0, "How do I get a hotfix out before Thursday's train?"),
        ("ben-carter", 12, "Open the PR with the `hotfix` label and get one approval, then ping here and I'll do an off-train promote. If it has a migration, loop in the on-call SRE first, since rolling back a migration needs them."),
        ("jordan-blake", 30, "And watch Sentry for 15 minutes after the promote. Roll back from the deploy dashboard if anything spikes."),
    ]),
]

threads.GOLDEN_IDS.update(g[0] for g in GOLDEN)


def _start(days_ago: int, now: datetime) -> datetime:
    day = (now - timedelta(days=days_ago)).date()
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return datetime(day.year, day.month, day.day, 17, 15, tzinfo=UTC)  # 10:15 Pacific


def golden_records(people: dict[str, Person], now: datetime) -> list[tuple[Artifact, list[Event]]]:
    out = []
    for thread_id, channel, topic_ids, days_ago, messages in GOLDEN:
        start = _start(days_ago, now)
        msgs = [(who, start + timedelta(minutes=m), text) for who, m, text in messages]
        out.append(records_from_messages(thread_id, channel, topic_ids, msgs, people))
    return out
