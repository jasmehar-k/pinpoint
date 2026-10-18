from datetime import UTC, date, datetime, time, timedelta

import pytest

from graph.availability import TZ, availability, booked_pct, demo_week, factor, free_slots, merge
from org import load_org
from schema import Meeting
from seed.meetings import TARGETS, TOLERANCE, generate, open_reviews

PEOPLE = load_org().people
SATURDAY = date(2026, 10, 17)
WEDNESDAY = date(2026, 10, 21)


def _m(person_ids, day, start, minutes, id_="m"):
    s = datetime.combine(day, start, TZ)
    return Meeting(id=id_, title="x", attendees=person_ids, start=s, end=s + timedelta(minutes=minutes))


def test_demo_week_rolls_forward_on_weekends():
    assert demo_week(SATURDAY)[0] == date(2026, 10, 19)
    assert demo_week(WEDNESDAY)[0] == date(2026, 10, 19)
    assert demo_week(date(2026, 10, 26))[-1] == date(2026, 10, 30)


def test_merge_overlaps():
    a = datetime(2026, 10, 19, 9, tzinfo=TZ)
    h = timedelta(hours=1)
    assert merge([(a, a + h), (a + h / 2, a + 2 * h), (a + 3 * h, a + 4 * h)]) == [(a, a + 2 * h), (a + 3 * h, a + 4 * h)]


def test_booked_pct_merges_double_bookings():
    days = demo_week(SATURDAY)
    meetings = [_m(["a"], days[0], time(9), 240), _m(["a"], days[0], time(11), 120)]  # 9-1 and 11-1
    assert booked_pct(meetings, "a", days) == pytest.approx(240 / 2400)


def test_factor_matches_fixture_numbers():
    assert factor(0.78, 6) == 0.154
    assert factor(0.85, 9) == 0.083
    assert factor(0.35, 2) == 0.585
    assert factor(0.0, 50) == 0.5  # reviews are capped


def test_free_slots_skip_busy_and_past():
    days = demo_week(SATURDAY)
    meetings = [_m(["a"], days[0], time(9), 60), _m(["b"], days[0], time(10), 30)]
    now = datetime.combine(days[0], time(9), TZ)
    slots = [s.start.astimezone(TZ).time() for s in free_slots(meetings, ["a", "b"], days[:1], now)]
    assert slots[:2] == [time(10, 30), time(11)]
    assert len(slots) == 16 - 3
    later = datetime.combine(days[0], time(16), TZ)
    assert len(free_slots([], ["a"], days[:1], later)) == 2


@pytest.fixture(scope="module")
def calendar():
    return generate(PEOPLE, SATURDAY)


def test_targets_are_hit(calendar):
    meetings, targets = calendar
    days = demo_week(SATURDAY)
    for person, target in TARGETS.items():
        assert booked_pct(meetings, person, days) == pytest.approx(target, abs=TOLERANCE + 0.01), person
    for p in PEOPLE:
        assert booked_pct(meetings, p.id, days) <= targets[p.id] + TOLERANCE + 0.01, p.id


def test_no_double_booking_and_working_hours(calendar):
    meetings, _ = calendar
    for p in PEOPLE:
        mine = sorted((m.start, m.end) for m in meetings if p.id in m.attendees)
        for (_, e1), (s2, _) in zip(mine, mine[1:]):
            assert e1 <= s2, p.id
    for m in meetings:
        s, e = m.start.astimezone(TZ), m.end.astimezone(TZ)
        assert s.date() == e.date() and time(9) <= s.time() and e.time() <= time(17)


def test_everyone_has_standups_and_a_one_on_one(calendar):
    meetings, _ = calendar
    for p in PEOPLE:
        titles = [m.title for m in meetings if p.id in m.attendees]
        assert sum(t.endswith("standup") for t in titles) == 5, p.id
        if p.manager:
            assert any(t.startswith("1:1") for t in titles), p.id


def test_demo_slot_stays_free(calendar):
    meetings, _ = calendar
    wed = demo_week(SATURDAY)[2]
    now = datetime.combine(demo_week(SATURDAY)[0], time(8), TZ)
    slots = {s.start for s in free_slots(meetings, ["priya-shah", "marcus-lee"], [wed], now)}
    assert datetime.combine(wed, time(10, 30), TZ) in slots


def test_marcus_outranks_dana_on_availability(calendar):
    meetings, _ = calendar
    now = datetime.combine(demo_week(SATURDAY)[0], time(8), TZ)
    res = availability(meetings, ["dana-okafor", "marcus-lee", "victor-hale"], open_reviews(PEOPLE), SATURDAY, now)
    f = {a.person_id: a.factor for a in res.people}
    assert f["marcus-lee"] > 0.5 > 0.2 > f["dana-okafor"] > f["victor-hale"]


def test_generation_is_deterministic():
    a, _ = generate(PEOPLE, SATURDAY)
    b, _ = generate(PEOPLE, SATURDAY)
    assert [(m.title, m.start) for m in a] == [(m.title, m.start) for m in b]
