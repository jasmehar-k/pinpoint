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
