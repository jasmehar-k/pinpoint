"""Bandwidth: how booked people are this week, and when they're all free.

Kept behind get_availability() so a real calendar API can replace the meetings table later.

    factor = (1 - booked_pct) * (1 - min(open_reviews, 10) / 20)

So a free person with no reviews is 1.0, someone 78% booked with 6 open reviews is 0.154.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from schema import Availability, AvailabilityResponse, Meeting, Slot

TZ = ZoneInfo("America/Los_Angeles")
DAY_START, DAY_END = time(9), time(17)
SLOT = timedelta(minutes=30)
REVIEW_CAP = 10


def demo_week(today: date) -> list[date]:
    """Mon to Fri of this week, or of next week when today is a weekend."""
    monday = today - timedelta(days=today.weekday())
    if today.weekday() >= 5:
        monday += timedelta(days=7)
    return [monday + timedelta(days=i) for i in range(5)]


def working_intervals(days: list[date]) -> list[tuple[datetime, datetime]]:
    return [(datetime.combine(d, DAY_START, TZ), datetime.combine(d, DAY_END, TZ)) for d in days]


def merge(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    out = []
    for start, end in sorted(intervals):
        if out and start <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], end))
        else:
            out.append((start, end))
    return out


def _overlap(a: tuple[datetime, datetime], b: tuple[datetime, datetime]) -> timedelta:
    return max(min(a[1], b[1]) - max(a[0], b[0]), timedelta(0))


def busy_intervals(meetings: list[Meeting], person_id: str) -> list[tuple[datetime, datetime]]:
    return merge([(m.start, m.end) for m in meetings if person_id in m.attendees])


def booked_pct(meetings: list[Meeting], person_id: str, days: list[date]) -> float:
    work = working_intervals(days)
    total = sum((e - s for s, e in work), timedelta(0))
    busy = sum((_overlap(b, w) for b in busy_intervals(meetings, person_id) for w in work), timedelta(0))
    return round(busy / total, 3) if total else 0.0


def factor(booked: float, open_reviews: int) -> float:
    return round((1 - booked) * (1 - min(open_reviews, REVIEW_CAP) / (2 * REVIEW_CAP)), 3)


def free_slots(meetings: list[Meeting], person_ids: list[str], days: list[date],
               now: datetime) -> list[Slot]:
    """30-minute slots in working hours, in the future, free for everyone listed."""
    busy = merge([iv for p in person_ids for iv in busy_intervals(meetings, p)])
    slots = []
    for day_start, day_end in working_intervals(days):
        t = day_start
        while t + SLOT <= day_end:
            slot = (t, t + SLOT)
            if t >= now and not any(_overlap(slot, b) for b in busy):
                slots.append(Slot(start=t, end=t + SLOT))
            t += SLOT
    return slots


def availability(meetings: list[Meeting], person_ids: list[str], open_reviews: dict[str, int],
                 today: date, now: datetime) -> AvailabilityResponse:
    days = demo_week(today)
    people = []
    for p in person_ids:
        pct = booked_pct(meetings, p, days)
        reviews = open_reviews.get(p, 0)
        people.append(Availability(person_id=p, booked_pct=pct, open_reviews=reviews, factor=factor(pct, reviews)))
    work = working_intervals(days)
    return AvailabilityResponse(window_start=work[0][0], window_end=work[-1][1], people=people,
                                mutual_free_slots=free_slots(meetings, person_ids, days, now))


# ---- DB layer ----

def load_meetings(conn, person_ids: list[str], days: list[date]) -> list[Meeting]:
    work = working_intervals(days)
    rows = conn.execute(
        """
        select id, title, attendees, start_at, end_at, recurring from meetings
        where attendees && %s and end_at > %s and start_at < %s
        """,
        (person_ids, work[0][0], work[-1][1]),
    ).fetchall()
    return [Meeting(id=r[0], title=r[1], attendees=r[2], start=r[3], end=r[4], recurring=r[5]) for r in rows]


def get_availability(conn, person_ids: list[str], now: datetime) -> AvailabilityResponse:
    today = now.astimezone(TZ).date()
    meetings = load_meetings(conn, person_ids, demo_week(today))
    reviews = dict(conn.execute("select id, open_reviews from people where id = any(%s)", (person_ids,)).fetchall())
    return availability(meetings, person_ids, reviews, today, now)
