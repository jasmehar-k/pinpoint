from datetime import UTC, datetime, timedelta

import pytest

from graph.experts import Candidate, dominant_topic, evidence_summary, rank_candidates
from graph.scoring import EventRow, contribution, decay, score_edges
from search import Hit

NOW = datetime(2026, 10, 17, tzinfo=UTC)


def _row(person, type_, artifact="a1", days_ago=0, topic="messaging"):
    return EventRow(person, type_, artifact, f"PR {artifact}", f"https://x/{artifact}",
                    NOW - timedelta(days=days_ago), topic)


def test_decay_halves_every_90_days():
    assert decay(NOW, NOW) == 1
    assert decay(NOW - timedelta(days=90), NOW) == pytest.approx(0.5)
    assert decay(NOW - timedelta(days=180), NOW) == pytest.approx(0.25)
    assert decay(NOW + timedelta(days=1), NOW) == 1  # future timestamps don't boost


def test_contribution_uses_type_weights():
    assert contribution("authored", NOW, NOW) == 1.0
    assert contribution("reviewed", NOW, NOW) == 0.7
    assert contribution("answered", NOW - timedelta(days=90), NOW) == pytest.approx(0.4)


def test_score_edges_sums_and_keeps_receipts():
    rows = [
        _row("dana", "authored", "a1"),
        _row("dana", "authored", "a2", days_ago=90),
        _row("dana", "reviewed", "a3"),
        _row("dana", "asked", "a4"),
        _row("dana", "authored", "a5", topic=None),  # untagged: ignored
        _row("marcus", "reviewed", "a1"),
    ]
    edges = score_edges(rows, NOW)
    dana = edges[("dana", "messaging")]
    assert dana.score == pytest.approx(1.0 + 0.5 + 0.7 + 0.1)
    assert dict(dana.counts) == {"authored": 2, "reviewed": 1, "asked": 1}
    assert [e.artifact_id for e in dana.top_evidence()] == ["a1", "a3", "a2"]
    assert dana.last_active == NOW
    assert ("dana", None) not in edges


def _hit(id_, sim, topics=("messaging",)):
    return Hit(id=id_, source="github", title=id_, url=f"https://x/{id_}", timestamp=NOW,
               similarity=sim, snippet="", topics=list(topics))


def test_rank_candidates_weights_by_similarity_and_excludes_asker():
    hits = [_hit("a1", 0.9), _hit("a2", 0.5)]
    events = [
        _row("dana", "authored", "a1"),
        _row("marcus", "reviewed", "a1"),
        _row("marcus", "authored", "a2"),
        _row("priya", "asked", "a1"),
        _row("ghost", "authored", "not-a-hit"),
    ]
    ranked = rank_candidates(hits, events, NOW, exclude={"priya"})
    assert [c.person_id for c in ranked] == ["marcus", "dana"]
    assert ranked[0].score == pytest.approx(0.9 * 0.7 + 0.5 * 1.0)


def test_top_evidence_dedupes_artifacts():
    c = Candidate("dana", evidence=[(1.0, _row("dana", "authored", "a1")),
                                    (0.9, _row("dana", "reviewed", "a1")),
                                    (0.5, _row("dana", "authored", "a2"))])
    assert [e.url for e in c.top_evidence()] == ["https://x/a1", "https://x/a2"]


def test_dominant_topic_is_similarity_weighted():
    hits = [_hit("a1", 0.9, ["billing"]), _hit("a2", 0.4, ["auth"]), _hit("a3", 0.4, ["auth"]), _hit("a4", 0.3, [])]
    assert dominant_topic(hits) == "billing"
    assert dominant_topic([_hit("a1", 0.9, [])]) is None


def test_evidence_summary_phrasing():
    assert evidence_summary({"authored": 128, "reviewed": 19}, "messaging", NOW - timedelta(days=1), NOW) == \
        "Authored 128 PRs in Messaging, reviewed 19, active 1 day ago"
    assert evidence_summary({"authored": 22, "reviewed": 55}, "messaging", NOW, NOW, ("Dana", 38)) == \
        "Reviewed 38 of Dana's Messaging PRs, authored 22 PRs in Messaging, active today"
    assert evidence_summary({"authored": 1, "answered": 1}, "billing", None, NOW) == \
        "Authored 1 PR in Billing, answered 1 question"
    assert evidence_summary({}, None, None, NOW) == "Related activity"
