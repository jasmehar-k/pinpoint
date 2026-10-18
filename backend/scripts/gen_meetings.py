"""Generate the demo week's fake calendars and open review counts. Rerunnable: replaces seeded
meetings, keeps meetings booked through Pinpoint (reset_demo clears those).

    uv run python -m scripts.gen_meetings
"""

from datetime import UTC, datetime

import db
from graph.availability import TZ, booked_pct, demo_week
from org import load_org
from seed.meetings import generate, open_reviews


def main() -> None:
    people = load_org().people
    today = datetime.now(UTC).astimezone(TZ).date()
    meetings, targets = generate(people, today)
    reviews = open_reviews(people)

    with db.connect(vector=False) as conn:
        with conn.cursor() as cur:
            cur.execute("delete from meetings where seeded")
            cur.executemany(
                """
                insert into meetings (id, title, attendees, start_at, end_at, recurring, seeded)
                values (%s, %s, %s, %s, %s, %s, true)
                """,
                [(m.id, m.title, m.attendees, m.start, m.end, m.recurring) for m in meetings],
            )
            cur.executemany("update people set open_reviews = %s where id = %s",
                            [(n, pid) for pid, n in reviews.items()])

    days = demo_week(today)
    print(f"{len(meetings)} meetings for {days[0]}..{days[-1]}")
    for p in sorted(people, key=lambda p: -booked_pct(meetings, p.id, days))[:8]:
        print(f"  {p.name:14} {booked_pct(meetings, p.id, days):.0%} booked, {reviews[p.id]} open reviews")


if __name__ == "__main__":
    main()
