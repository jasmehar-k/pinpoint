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
