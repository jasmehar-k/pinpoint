from datetime import date, datetime, time, timedelta

import pytest

from agent.compose import (drop_unlisted_people, fallback_answer, intent, parse_reply, pick_slot,
                           renumber_citations, routing_text, slot_label, slot_preference)
from graph.availability import TZ
from org import load_org
from schema import Availability, Expert, Slot
from search import Hit

PEOPLE = load_org().people


def _expert(pid, name, expertise, booked, badge, same_team=True, summary="Authored 10 PRs in Messaging"):
    return Expert(person_id=pid, name=name, team="Integrations", role="r", topic="messaging",
                  expertise=expertise, rank_score=0, evidence_summary=summary, evidence=[], badge=badge,
                  same_team=same_team,
                  availability=Availability(person_id=pid, booked_pct=booked, open_reviews=0, factor=1 - booked))


DANA = _expert("dana-okafor", "Dana Okafor", 9.0, 0.78, "busy", summary="Authored 128 PRs in Messaging, reviewed 19")
MARCUS = _expert("marcus-lee", "Marcus Lee", 5.6, 0.35, "recommended",
                 summary="Reviewed 38 of Dana's Messaging PRs, authored 22 PRs in Messaging")
EXPERTS = [MARCUS, DANA]


@pytest.mark.parametrize("message,expected", [
    ("can you book time with him on Wednesday?", "schedule"),
    ("schedule a meeting", "schedule"),
    ("find some time for us", "schedule"),
    ("how does calendar sync work?", "question"),
    ("message Dana instead", "redirect"),
    ("can you ask Dana?", "redirect"),
    ("who wrote the billing webhooks?", "question"),
])
def test_intent(message, expected):
    assert intent(message, EXPERTS) == expected


def test_no_follow_ups_without_experts():
    assert intent("book time", []) == "question"


@pytest.mark.parametrize("message,expected", [
    ("Wednesday at 10:30am", (2, time(10, 30), None)),
    ("thu 2pm", (3, time(14), None)),
    ("tomorrow morning", (None, None, "morning")),
    ("friday afternoon for 30 minutes", (4, None, "afternoon")),
    ("at 2 on tuesday", (1, None, None)),  # bare number isn't a time
    ("tuesday at 2:00", (1, time(14), None)),
])
def test_slot_preference(message, expected):
    assert slot_preference(message) == expected


MONDAY = date(2026, 10, 19)


def _slots(*specs):
    out = []
    for day_offset, h, m in specs:
        s = datetime.combine(MONDAY + timedelta(days=day_offset), time(h, m), TZ)
        out.append(Slot(start=s, end=s + timedelta(minutes=30)))
    return out


def test_pick_slot():
    slots = _slots((0, 9, 0), (2, 10, 0), (2, 10, 30), (2, 15, 0), (3, 11, 0))
    assert pick_slot(slots, "wednesday 10:30am") == (slots[2], True)
    assert pick_slot(slots, "wed afternoon") == (slots[3], True)
    assert pick_slot(slots, "wednesday at 11am") == (slots[2], False)  # nearest that day
    assert pick_slot(slots, "whenever works") == (slots[0], False)
    assert pick_slot([], "wed") == (None, False)


def test_slot_label():
    assert slot_label(_slots((2, 10, 30))[0]) == "Wed 10:30 AM"
    assert slot_label(_slots((3, 14, 0))[0]) == "Thu 2 PM"


def test_parse_reply():
    assert parse_reply('```json\n{"answer": "It uses webhooks [1].", "dm": "Hi"}\n```') == \
        {"answer": "It uses webhooks [1].", "dm": "Hi"}
    with pytest.raises(ValueError):
        parse_reply('{"answer": ""}')


def test_renumber_citations_drops_bad_markers_and_renumbers():
    text, order = renumber_citations("Webhooks enqueue a job [3]. The cron is a fallback [1, 3] [9].", 4)
    assert text == "Webhooks enqueue a job [1]. The cron is a fallback [2][1]."
    assert order == [2, 0]


def test_drop_unlisted_people():
    text = "Webhooks trigger sync [1]. Victor Hale designed it. Marcus Lee reviewed it."
    assert drop_unlisted_people(text, PEOPLE, {"marcus-lee"}) == "Webhooks trigger sync [1]. Marcus Lee reviewed it."


def test_fallback_answer():
    hits = [Hit(id=f"a{i}", source="github", title=f"PR {i}", url="u", timestamp=datetime.now(TZ),
                similarity=0.5, snippet="") for i in range(5)]
    text, order = fallback_answer(hits)
    assert "PR 0 [1]; PR 1 [2]; PR 2 [3]" in text and order == [0, 1, 2]


def test_routing_when_top_expert_is_busy():
    text, to = routing_text(EXPERTS)
    assert to is MARCUS
    assert text == ("Dana knows this best but is 78% booked this week. Marcus reviewed 38 of Dana's Messaging PRs, "
                    "is on your team, and is 35% booked, so I'd start with Marcus. I drafted a message to Marcus below.")


def test_routing_when_top_expert_is_free():
    free_dana = DANA.model_copy(update={"badge": "recommended"})
    text, to = routing_text([free_dana])
    assert to is free_dana and text.startswith("Dana knows this best (authored 128 PRs in Messaging)")


def test_routing_when_everyone_is_busy():
    busy_marcus = MARCUS.model_copy(update={"badge": "busy"})
    text, to = routing_text([busy_marcus, DANA])
    assert to is DANA and text.startswith("Everyone who knows this well is busy")


def test_routing_with_no_experts():
    assert routing_text([]) == ("I couldn't find anyone with history on this yet.", None)


def test_answer_sources_cap_threads():
    from agent.chat import answer_sources
    srcs = ["seed", "seed", "slack", "seed", "github", "seed", "github", "github", "github", "github"]
    hits = [Hit(id=f"a{i}", source=s, title="t", url="u", timestamp=datetime.now(TZ), similarity=1 - i / 100,
                snippet="") for i, s in enumerate(srcs)]
    picked = answer_sources(hits)
    assert [h.id for h in picked] == ["a0", "a1", "a2", "a4", "a6", "a7"]


def test_tidy_dm():
    from agent.compose import tidy_dm
    marcus = next(p for p in PEOPLE if p.id == "marcus-lee")
    assert tidy_dm("Hey Marcus Lee, I want to understand sync—specifically webhooks.", marcus) == \
        "Hey Marcus, I want to understand sync, specifically webhooks."


def test_cite_top_sources():
    from agent.compose import cite_top_sources
    assert cite_top_sources("Open a hotfix PR.", 6) == ("Open a hotfix PR. (Sources: [1][2])", [0, 1])
    assert cite_top_sources("x", 1) == ("x (Sources: [1])", [0])


def _pr_hit(n):
    return Hit(id=f"github:pr:{n}", source="github", title=f"PR {n}", url="u", timestamp=datetime.now(TZ),
               similarity=0.5, snippet="")


def test_cite_mentioned_prs_points_at_the_right_source():
    from agent.compose import cite_mentioned_prs
    hits = [_pr_hit(1), _pr_hit(27947), _pr_hit(3), _pr_hit(4), _pr_hit(5), _pr_hit(26180)]
    text = "Webhooks enqueue a job, introduced in PR #26180 [2]. See #99999 too."
    assert cite_mentioned_prs(text, hits) == "Webhooks enqueue a job, introduced in PR #26180 [6] [2]. See #99999 too."
    already = "Fixed in #26180 [6]."
    assert cite_mentioned_prs(already, hits) == already


def test_wrong_citation_flows_through_renumbering():
    from agent.compose import cite_mentioned_prs
    hits = [_pr_hit(1), _pr_hit(27947), _pr_hit(3), _pr_hit(4), _pr_hit(5), _pr_hit(26180)]
    text, order = renumber_citations(cite_mentioned_prs("Introduced in #26180 [2].", hits), len(hits))
    assert text == "Introduced in #26180 [1][2]." and order == [5, 1]
