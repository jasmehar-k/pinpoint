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


# ---- availability reranking ----

from graph.experts import apply_availability  # noqa: E402
from schema import Availability, Expert  # noqa: E402


def _expert(pid, expertise, same_team=False):
    return Expert(person_id=pid, name=pid, team="T", role="r", topic="messaging", expertise=expertise,
                  rank_score=expertise, evidence_summary="", evidence=[], same_team=same_team)


def _avail(pid, booked, reviews):
    from graph.availability import factor
    return Availability(person_id=pid, booked_pct=booked, open_reviews=reviews, factor=factor(booked, reviews))


def test_busy_top_expert_loses_to_free_reviewer():
    experts = [_expert("dana", 9.0, True), _expert("marcus", 5.6, True), _expert("victor", 5.5)]
    avail = [_avail("dana", 0.78, 6), _avail("marcus", 0.35, 2), _avail("victor", 0.85, 9)]
    ranked = apply_availability(experts, avail)
    assert [(e.person_id, e.badge) for e in ranked] == [
        ("marcus", "recommended"), ("dana", "busy"), ("victor", "busy")]
    assert ranked[0].rank_score == pytest.approx(5.6 * 0.585 * 1.1, abs=0.01)
    assert ranked[0].availability.booked_pct == 0.35


def test_same_team_breaks_close_calls():
    experts = [_expert("other", 5.0), _expert("mine", 4.8, same_team=True)]
    avail = [_avail("other", 0.3, 0), _avail("mine", 0.3, 0)]
    assert apply_availability(experts, avail)[0].person_id == "mine"


def test_everyone_busy_means_no_recommendation():
    ranked = apply_availability([_expert("a", 5.0)], [_avail("a", 0.9, 0)])
    assert ranked[0].badge == "busy"


def test_relevant_keeps_hits_near_the_best():
    from graph.experts import relevant
    hits = [_hit("a", 0.82), _hit("b", 0.75), _hit("c", 0.72), _hit("d", 0.70)]
    assert [h.id for h in relevant(hits)] == ["a", "b", "c"]
    assert relevant([]) == []


def test_bus_factor():
    from graph.view import bus_factor
    assert bus_factor([("dana", 96), ("victor", 51), ("marcus", 42)]) == (["dana"], "victor")
    assert bus_factor([("ben", 6.7), ("jordan", 4.4), ("sam", 2.5)]) == (["ben", "jordan"], "sam")
    assert bus_factor([("a", 10), ("b", 9), ("c", 8)]) == (["a", "b", "c"], None)
    assert bus_factor([("a", 0.5)]) == ([], "a")  # nobody above the minimum score
    assert bus_factor([]) == ([], None)


def test_corrections_demote_and_redirect():
    from graph.experts import apply_corrections

    def cands():
        return [Candidate("dana", 9.0), Candidate("marcus", 5.0), Candidate("ken", 1.0)]

    once = apply_corrections(cands(), [("dana", "not_owner", None)])
    assert [(c.person_id, c.score) for c in once] == [("marcus", 5.0), ("dana", 4.5), ("ken", 1.0)]
    twice = apply_corrections(cands(), [("dana", "not_owner", None)] * 2)
    assert twice[0].person_id == "marcus" and twice[1].score == 2.25
    redirected = apply_corrections(cands(), [("dana", "redirect", "ken")])
    assert [c.person_id for c in redirected] == ["ken", "marcus", "dana"] and redirected[0].score == 9.0
    new_person = apply_corrections(cands(), [("dana", "redirect", "lena")])
    assert new_person[0].person_id == "lena"
    assert all(c.person_id != "priya" for c in apply_corrections(cands(), [("dana", "redirect", "priya")], {"priya"}))
    assert apply_corrections(cands(), [("nobody", "not_owner", None)])[0].person_id == "dana"


def test_named_topic_uses_the_files_a_pr_touches():
    from graph.experts import named_topic
    S, F = "packages/twenty-server/src/", "packages/twenty-front/src/modules/"
    billing_pr = [S + "engine/core-modules/billing/a.ts", S + "engine/core-modules/billing/b.ts",
                  S + "engine/core-modules/auth/c.ts", F + "ui/x.tsx", F + "ui/y.tsx", F + "ui/z.tsx"]
    assert named_topic(billing_pr) == "billing"  # most files among specific topics; frontend is the catch-all
    assert named_topic([F + "ui/x.tsx"]) == "frontend"
    assert named_topic(["README.md"]) is None
