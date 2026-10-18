"""Golden demo tests against the real DB. Run after every pipeline step:

    uv run pytest -m demo

These guard the demo story. If one fails, a pipeline change broke what judges will see.
"""

from collections import Counter

import pytest

import config
import db
from search import search_artifacts

pytestmark = [
    pytest.mark.demo,
    pytest.mark.skipif(not config.DATABASE_URL, reason="needs DATABASE_URL"),
]


@pytest.fixture(scope="module")
def conn():
    with db.connect() as c:
        yield c


def _pr_numbers(hits):
    return {h.id.removeprefix("github:pr:") for h in hits if h.id.startswith("github:pr:")}


# (question, topic most of the top 5 should belong to)
TOPIC_CASES = [
    ("How does inbound email sync work?", "messaging"),
    ("Why does my Gmail mailbox import keep failing?", "messaging"),
    ("How do calendar events get synced from Google Calendar?", "calendar"),
    ("How do workflow triggers and actions run?", "workflow"),
    ("How are subscriptions and plan upgrades billed?", "billing"),
    ("How does SSO login work?", "auth"),
    ("How do I add a custom field to an object?", "metadata"),
]


@pytest.mark.parametrize("question,topic", TOPIC_CASES)
def test_top_hits_are_on_topic(conn, question, topic):
    hits = search_artifacts(conn, question, k=5)
    on_topic = sum(topic in h.topics for h in hits)
    assert on_topic >= 3, [(h.title, h.topics) for h in hits]


# (question, PR numbers of which at least one must be in the top k)
PR_CASES = [
    ("How does inbound email sync get triggered?", {"26180", "26181"}, 10),
    ("Why are sent Gmail emails duplicated after sync?", {"27688"}, 5),
    ("IMAP connection issues with non standard servers", {"26843", "24888"}, 10),
]


@pytest.mark.parametrize("question,expected,k", PR_CASES)
def test_known_prs_are_found(conn, question, expected, k):
    hits = search_artifacts(conn, question, k=k)
    assert _pr_numbers(hits) & expected, [h.title for h in hits]


def test_every_artifact_is_embedded(conn):
    missing = conn.execute("select count(*) from artifacts where embedding is null").fetchone()[0]
    assert missing == 0


# ---- expert ranking (before availability) ----

from graph.experts import find_experts  # noqa: E402


def _ranked_ids(conn, question):
    return [e.person_id for e in find_experts(conn, question, asker_id="priya-shah")]


def test_email_sync_ranks_dana_then_her_reviewers(conn):
    ids = _ranked_ids(conn, "How does inbound email sync work?")
    assert ids[0] == "dana-okafor"
    assert set(ids[:3]) == {"dana-okafor", "marcus-lee", "victor-hale"}


def test_marcus_evidence_names_dana(conn):
    marcus = next(e for e in find_experts(conn, "How does inbound email sync work?", asker_id="priya-shah")
                  if e.person_id == "marcus-lee")
    assert marcus.topic == "messaging"
    assert marcus.evidence_summary.startswith("Reviewed ") and "of Dana's Messaging PRs" in marcus.evidence_summary
    assert marcus.same_team


@pytest.mark.parametrize("question,owner", [
    ("How are subscriptions and plan upgrades billed?", "isabel-moreno"),
    ("How do workflow triggers and actions run?", "elena-petrova"),
])
def test_topic_owners_rank_first(conn, question, owner):
    assert _ranked_ids(conn, question)[0] == owner


def test_asker_is_never_an_expert(conn):
    for question, _ in TOPIC_CASES:
        assert "priya-shah" not in _ranked_ids(conn, question)


def test_evidence_urls_exist(conn):
    for e in find_experts(conn, "How does inbound email sync work?"):
        for ev in e.evidence:
            assert conn.execute("select 1 from artifacts where url = %s", (ev.url,)).fetchone(), ev.url


# ---- availability (needs scripts.gen_meetings) ----

from datetime import UTC, datetime  # noqa: E402

from artifacts import get_artifact  # noqa: E402
from graph.availability import get_availability  # noqa: E402
from graph.experts import apply_availability  # noqa: E402


def test_demo_story_marcus_recommended_over_busy_dana(conn):
    experts = find_experts(conn, "How does inbound email sync work?", asker_id="priya-shah")
    avail = get_availability(conn, [e.person_id for e in experts], datetime.now(UTC))
    ranked = apply_availability(experts, avail.people)
    assert (ranked[0].person_id, ranked[0].badge) == ("marcus-lee", "recommended")
    badges = {e.person_id: e.badge for e in ranked}
    assert badges["dana-okafor"] == badges["victor-hale"] == "busy"


def test_priya_and_marcus_have_wednesday_1030(conn):
    slots = get_availability(conn, ["priya-shah", "marcus-lee"], datetime.now(UTC)).mutual_free_slots
    assert any(s.start.strftime("%a %H:%M") == "Wed 10:30" for s in slots) or datetime.now(UTC).weekday() == 2


def test_artifact_page_for_a_pr(conn):
    a = get_artifact(conn, "github:pr:26180")
    assert a.kind == "pr" and a.messages is None and "messaging" in a.topics
    assert ("authored", "dana-okafor") in [(p.type, p.person_id) for p in a.people]


# ---- full chat flow (fake LLM, real DB) ----

import json as _json  # noqa: E402
from types import SimpleNamespace  # noqa: E402

from agent import actions as _actions  # noqa: E402
from agent.chat import handle  # noqa: E402
from schema import ChatRequest  # noqa: E402


class FakeLLM:
    """Returns a fixed reply with one bad citation and one name find_experts didn't return."""

    def __init__(self):
        content = _json.dumps({
            "answer": "Provider webhooks enqueue a sync job directly [1]. Ravi Menon designed it. "
                      "The cron is the fallback [2][9].",
            "dm": "Hi Marcus, I'm Priya and just joined Integrations. Could you walk me through how webhook "
                  "sync works (#26180)? 30 minutes this week would be great.",
        })
        message = SimpleNamespace(content=content)
        self.chat = SimpleNamespace(completions=SimpleNamespace(
            create=lambda **_: SimpleNamespace(choices=[SimpleNamespace(message=message)])))


@pytest.fixture
def cleanup(conn):
    created = []
    yield created
    for kind, id_ in created:
        table = "meetings" if kind == "meeting" else "pending_actions"
        conn.execute(f"delete from {table} where id = %s", (id_,))
    conn.commit()


def test_full_demo_flow(conn, cleanup, monkeypatch):
    monkeypatch.setattr("config.MODE", "seeded")  # never DM a real person from a test
    first = handle(conn, ChatRequest(message="How does inbound email sync work?", user="priya-shah"), client=FakeLLM())

    text = first.reply.text
    assert "Ravi Menon designed it" not in text and "[9]" not in text  # not in find_experts
    assert [c.id for c in first.reply.citations] == ["1", "2"]
    assert "so I'd start with Marcus" in text
    assert first.experts[0].person_id == "marcus-lee" and first.experts[0].badge == "recommended"
    dm = first.pending_actions[0]
    cleanup.append(("action", dm.id))
    assert (dm.kind, dm.status, dm.payload.to) == ("send_message", "pending", "marcus-lee")

    done = _actions.approve(conn, dm.id, {"to": "marcus-lee", "text": "edited text"})
    assert done.status == "executed" and done.result == {"delivery": "simulated", "to": "marcus-lee"}
    assert done.payload.text == "edited text"
    assert _actions.approve(conn, dm.id).executed_at == done.executed_at  # double click: runs once

    second = handle(conn, ChatRequest(message="can you book time with Marcus wednesday morning?",
                                      user="priya-shah", conversation_id=first.conversation_id))
    invite = second.pending_actions[0]
    cleanup.append(("action", invite.id))
    assert invite.kind == "schedule_meeting" and invite.payload.attendees == ["priya-shah", "marcus-lee"]
    assert second.availability and second.reply.text.startswith(("You and Marcus are both free", "Marcus isn't free"))

    booked = _actions.approve(conn, invite.id)
    assert booked.status == "executed", booked.result
    cleanup.append(("meeting", booked.result["meeting_id"]))
    slots = get_availability(conn, ["priya-shah", "marcus-lee"], datetime.now(UTC)).mutual_free_slots
    assert invite.payload.slot.start not in {s.start for s in slots}


def test_redirect_drafts_to_the_named_expert(conn, cleanup):
    first = handle(conn, ChatRequest(message="How does inbound email sync work?", user="priya-shah"), client=FakeLLM())
    cleanup.append(("action", first.pending_actions[0].id))
    second = handle(conn, ChatRequest(message="message Dana instead", user="priya-shah",
                                      conversation_id=first.conversation_id))
    cleanup.append(("action", second.pending_actions[0].id))
    assert second.pending_actions[0].payload.to == "dana-okafor"
    assert "Dana is 78% booked" in second.reply.text


# ---- seeded threads ----

def test_golden_thread_page(conn):
    a = get_artifact(conn, "seed-thread-0042")
    assert [m.person_id for m in a.messages] == ["aisha-bello", "dana-okafor", "marcus-lee", "aisha-bello"]
    assert a.url == "/artifacts/seed-thread-0042" and a.topics == ["messaging"]


@pytest.mark.parametrize("question,owners", [
    ("How do I ship a hotfix before the release train?", {"ben-carter", "jordan-blake", "sam-patel"}),
    ("Who handles on-call handover and paging?", {"sam-patel", "jordan-blake", "daniel-novak"}),
])
def test_non_code_topics_route_to_ops(conn, question, owners):
    assert _ranked_ids(conn, question)[0] in owners


def test_failed_booking_can_be_retried_with_another_slot(conn, cleanup):
    from schema import ScheduleMeetingPayload
    attendees = ["priya-shah", "marcus-lee"]
    free = get_availability(conn, attendees, datetime.now(UTC)).mutual_free_slots
    busy_slot = free[0]
    # take the first free slot with a throwaway meeting, then try to book it
    blocker = "mtg-test-blocker"
    conn.execute("insert into meetings (id, title, attendees, start_at, end_at, seeded) values (%s, 'blocker', %s, %s, %s, false)",
                 (blocker, attendees, busy_slot.start, busy_slot.end))
    conn.commit()
    cleanup.append(("meeting", blocker))
    action = _actions.create(conn, "schedule_meeting",
                             ScheduleMeetingPayload(title="t", attendees=attendees, slot=busy_slot), "priya-shah")
    cleanup.append(("action", action.id))

    failed = _actions.approve(conn, action.id)
    assert failed.status == "failed" and "no longer free" in failed.result["error"]

    retry = _actions.approve(conn, action.id, {"title": "t", "attendees": attendees,
                                               "slot": free[1].model_dump(mode="json")})
    assert retry.status == "executed", retry.result
    cleanup.append(("meeting", retry.result["meeting_id"]))
    assert _actions.approve(conn, action.id).result == retry.result  # and now it's done for good


def test_search_can_leave_out_an_artifact(conn):
    from search import search_artifacts
    top = search_artifacts(conn, "How does inbound email sync work?", k=3)
    rest = search_artifacts(conn, "How does inbound email sync work?", k=3, exclude=(top[0].id,))
    assert top[0].id not in {h.id for h in rest} and rest[0].id == top[1].id
