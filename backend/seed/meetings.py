"""Fake calendars for the demo week. Deterministic, so the demo looks the same every run.

Shared meetings first (standups, 1:1s, project meetings), then solo blocks ("Interview loop",
"Customer call") until each person hits their booked target. Some targets are fixed by the
demo story; the rest are random but stable.
"""

import random
from datetime import date, datetime, time, timedelta

from graph.availability import DAY_END, DAY_START, TZ, booked_pct, demo_week, merge
from schema import Meeting, Person

TARGETS = {
    "dana-okafor": 0.78, "victor-hale": 0.85, "lena-fischer": 0.72, "elena-petrova": 0.70,
    "marcus-lee": 0.35, "priya-shah": 0.22,
}
OPEN_REVIEWS = {"dana-okafor": 6, "victor-hale": 9, "marcus-lee": 2, "priya-shah": 0}
OTHER_TARGET_RANGE = (0.30, 0.60)
TOLERANCE = 0.015
# Wednesday 10:30-11:00 stays free for Priya and Marcus so the booking step always has its slot
PROTECTED = [({"priya-shah", "marcus-lee"}, 2, time(10, 30), time(11, 0))]

PROJECTS = {
    "Integrations": ["Email sync reliability", "Calendar sync v2 planning", "IMAP edge cases triage"],
    "Platform": ["Metadata API review", "Upgrade command planning", "Queue backlog review"],
    "Product": ["Workflow builder review", "Design critique", "Sprint planning"],
    "Core": ["Billing roadmap", "Release train retro", "Incident review"],
}
SOLO = ["Interview loop", "Customer call", "Hiring sync", "Architecture review", "Roadmap planning",
        "Design review prep", "Vendor call", "Focus: code review"]
ONBOARDING = ["Onboarding: dev environment", "Onboarding: codebase tour", "HR orientation", "Security training"]


class Calendar:
    def __init__(self, people: list[Person], days: list[date], rng: random.Random):
        self.people = {p.id: p for p in people}
        self.days = days
        self.rng = rng
        self.meetings: list[Meeting] = []
        self.targets = {
            p.id: TARGETS.get(p.id, round(rng.uniform(*OTHER_TARGET_RANGE), 2)) for p in people
        }

    def booked(self, person_id: str) -> float:
        return booked_pct(self.meetings, person_id, self.days)

    def _free(self, person_id: str, start: datetime, end: datetime) -> bool:
        for m in self.meetings:
            if person_id in m.attendees and m.start < end and start < m.end:
                return False
        for who, weekday, s, e in PROTECTED:
            day = self.days[weekday]
            ps, pe = datetime.combine(day, s, TZ), datetime.combine(day, e, TZ)
            if person_id in who and ps < end and start < pe:
                return False
        return True

    def _fits(self, person_id: str, minutes: int) -> bool:
        """Adding this meeting keeps the person at or under target."""
        return self.booked(person_id) + minutes / (len(self.days) * 8 * 60) <= self.targets[person_id] + TOLERANCE

    def add(self, title: str, attendees: list[str], minutes: int, recurring: bool = False,
            day: date | None = None, at: time | None = None) -> bool:
        """Place a meeting where every attendee is free. Returns False if nowhere fits."""
        days = [day] if day else self.rng.sample(self.days, len(self.days))
        for d in days:
            starts = [at] if at else [time(h, m) for h in range(DAY_START.hour, DAY_END.hour) for m in (0, 15, 30, 45)]
            if not at:
                self.rng.shuffle(starts)
            for t in starts:
                start = datetime.combine(d, t, TZ)
                end = start + timedelta(minutes=minutes)
                if end > datetime.combine(d, DAY_END, TZ):
                    continue
                if all(self._free(p, start, end) for p in attendees):
                    self.meetings.append(Meeting(
                        id=f"seed-mtg-{len(self.meetings) + 1:04d}", title=title, attendees=attendees,
                        start=start, end=end, recurring=recurring))
                    return True
        return False


def generate(people: list[Person], today: date, seed: int = 7) -> tuple[list[Meeting], dict[str, float]]:
    rng = random.Random(seed)
    cal = Calendar(people, demo_week(today), rng)
    by_team: dict[str, list[str]] = {}
    for p in people:
        by_team.setdefault(p.team, []).append(p.id)

    # 1. Daily standups
    for team, members in by_team.items():
        for d in cal.days:
            cal.add(f"{team} standup", members, 15, recurring=True, day=d, at=time(9, 30))

    # 2. Weekly 1:1 with manager
    for p in people:
        if p.manager:
            first = cal.people[p.manager].name.split()[0]
            cal.add(f"1:1 {p.name.split()[0]} / {first}", [p.id, p.manager], 30, recurring=True)

    # 3. Project meetings: 2 to 4 per person they organize, only inviting people with room
    for p in people:
        for _ in range(rng.randint(2, 4)):
            title = rng.choice(PROJECTS[p.team])
            minutes = rng.choice([45, 60])
            if not cal._fits(p.id, minutes):
                break
            others = [o for o in by_team[p.team] if o != p.id and cal._fits(o, minutes)]
            invitees = rng.sample(others, min(len(others), rng.randint(1, 3)))
            cal.add(title, [p.id, *invitees], minutes)

    # 4. Solo blocks until each person reaches their target
    for p in people:
        titles = ONBOARDING if p.id == "priya-shah" else SOLO
        for _ in range(60):
            gap = cal.targets[p.id] - cal.booked(p.id)
            if gap <= TOLERANCE:
                break
            options = [m for m in (90, 60, 45, 30, 15) if m / 2400 <= gap + TOLERANCE / 2] or [15]
            # Largest block that still fits somewhere; fall back to smaller ones as the week fills up
            if not any(cal.add(rng.choice(titles), [p.id], m) for m in options):
                break

    return cal.meetings, cal.targets


def open_reviews(people: list[Person], seed: int = 7) -> dict[str, int]:
    rng = random.Random(seed)
    return {p.id: OPEN_REVIEWS.get(p.id, rng.randint(0, 4) if p.github_login else 0) for p in people}
