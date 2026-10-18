import random
from collections import Counter
from datetime import UTC, datetime

import pytest

from org import load_org
from seed.golden import GOLDEN, golden_records
from seed.threads import (QUOTAS, ThreadPlan, answer_weights, leaked_names, parse_threads,
                          plan_threads, scrub_pr_refs, to_records)

NOW = datetime(2026, 10, 17, tzinfo=UTC)
ORG = load_org()
PEOPLE = {p.id: p for p in ORG.people}
SCORES = {"messaging": {"dana-okafor": 86, "victor-hale": 47, "marcus-lee": 35, "ken-watanabe": 20, "aisha-bello": 2}}


def test_answer_weights_damp_the_head_of_eng():
    w = answer_weights("messaging", SCORES["messaging"])
    assert sum(w.values()) == pytest.approx(1)
    assert set(w) == {"dana-okafor", "victor-hale", "marcus-lee", "ken-watanabe"}  # top 4 only
    assert w["dana-okafor"] > w["marcus-lee"] > w["victor-hale"]


def test_non_code_topics_use_fixed_pools():
    assert set(answer_weights("deploys", {})) == {"ben-carter", "jordan-blake", "sam-patel", "victor-hale"}


ALL_SCORES = {t: {"lena-fischer": 10, "ken-watanabe": 5, **SCORES.get(t, {})} for t in QUOTAS}


def _plans(scores=ALL_SCORES):
    return plan_threads(scores, ORG.people, NOW, random.Random(1), exclude_askers={"priya-shah"})


def test_plans_meet_quotas_and_are_deterministic():
    plans = _plans()
    assert Counter(p.topic for p in plans) == Counter(QUOTAS)
    assert [p.asker for p in plans] == [p.asker for p in _plans()]


def test_topics_with_nobody_to_answer_are_skipped():
    topics = {p.topic for p in _plans(SCORES)}
    assert topics == {"messaging", "deploys", "on-call"}  # fixed pools need no GitHub scores


def test_plan_invariants():
    plans = _plans()
    golden_ids = {g[0] for g in GOLDEN}
    assert len({p.id for p in plans}) == len(plans)
    for p in plans:
        assert p.asker not in answer_weights(p.topic, ALL_SCORES.get(p.topic, {}))
        assert p.asker != "priya-shah"
        assert p.id not in golden_ids
        assert p.start.weekday() < 5 and p.start < NOW
        assert len(p.answerers) == len(set(p.answerers))


def test_parse_threads():
    raw = '```json\n{"threads": [{"question": "q1", "answer": "a1", "followup": null}, {"question": "q2", "answer": "a2", "followup": "f2"}, {"question": "extra", "answer": "x"}]}\n```'
    assert parse_threads(raw, 2) == [
        {"question": "q1", "answer": "a1", "followup": None},
        {"question": "q2", "answer": "a2", "followup": "f2"},
    ]
    with pytest.raises(ValueError):
        parse_threads('{"threads": [{"question": "q", "answer": "a"}]}', 2)
    with pytest.raises(ValueError):
        parse_threads('{"threads": [{"question": "q", "answer": ""}]}', 1)
    with pytest.raises(ValueError):
        parse_threads("sorry, I can't", 1)


def test_scrub_pr_refs_keeps_only_context_prs():
    assert scrub_pr_refs("see #26180 and #99999", {"26180"}) == "see #26180 and a recent PR"


def test_leaked_names():
    assert leaked_names("ask Dana Okafor or neo773", ORG.people) == ["Dana Okafor", "neo773"]
    assert leaked_names("the on-call SRE knows", ORG.people) == []


def _plan(answerers):
    return ThreadPlan("seed-thread-9999", "messaging", "help", "aisha-bello", answerers, NOW,
                      context_prs=[{"number": 26180, "title": "t", "summary": "s"}])


def test_to_records_events_and_scrubbing():
    texts = {"question": "how does sync start?", "answer": "webhooks, see #26180 and #12345", "followup": "also the cron"}
    artifact, events = to_records(_plan(["dana-okafor", "marcus-lee"]), texts, PEOPLE)
    assert artifact.source == "seed" and artifact.topics == ["messaging"]
    assert artifact.url == "/artifacts/seed-thread-9999"
    assert artifact.text.splitlines()[1] == "Dana Okafor: webhooks, see #26180 and a recent PR"
    assert [(e.type, e.person_id) for e in events] == [
        ("asked", "aisha-bello"), ("answered", "dana-okafor"), ("answered", "marcus-lee")]


def test_no_followup_means_no_second_answer():
    texts = {"question": "q", "answer": "a", "followup": None}
    _, events = to_records(_plan(["dana-okafor", "marcus-lee"]), texts, PEOPLE)
    assert [e.person_id for e in events if e.type == "answered"] == ["dana-okafor"]


def test_golden_demo_thread():
    records = {a.id: (a, es) for a, es in golden_records(PEOPLE, NOW)}
    artifact, events = records["seed-thread-0042"]
    assert artifact.title.startswith("#help: how does inbound Gmail sync get triggered?")
    assert ("answered", "dana-okafor") in [(e.type, e.person_id) for e in events]
    # the asker's own "thanks" is not an answer
    assert [e.person_id for e in events if e.type == "answered"] == ["dana-okafor", "marcus-lee"]
    assert all(a.timestamp.weekday() < 5 for a, _ in records.values())


def test_drop_invented_paths():
    from seed.threads import drop_invented_paths
    text = "Sync starts from the webhook (#26180). The logic lives in `src/modules/email-sync/email-sync.service.ts`. Ask in #help."
    assert drop_invented_paths(text) == "Sync starts from the webhook (#26180). Ask in #help."
    assert drop_invented_paths("Version 2.20 shipped. See config.yml docs.") == "Version 2.20 shipped. See config.yml docs."


def test_drop_unsupported_identifiers():
    from seed.threads import drop_unsupported_identifiers
    context = "Sync message channels from webhooks: enqueues one job via BullMQ with keepLastIfActive"
    text = ("It uses BullMQ dedup (`keepLastIfActive`). Hook into the `afterSync` event. "
            "Subscribe to EmailSyncCompleted. Webhooks enqueue a job.")
    assert drop_unsupported_identifiers(text, context) == "It uses BullMQ dedup (`keepLastIfActive`). Webhooks enqueue a job."


def test_threads_with_nothing_verifiable_are_dropped():
    texts = {"question": "where is `EmailSyncService`?", "answer": "In EmailSyncService.", "followup": None}
    assert to_records(_plan(["dana-okafor"]), texts, PEOPLE) is None
