"""Upsert people.json and the fixed topic list into the DB."""

import db
from org import load_org
from topics import TOPICS


def main() -> None:
    org = load_org()
    with db.connect(vector=False) as conn:
        # Two passes so manager_id references resolve regardless of order.
        for p in org.people:
            conn.execute(
                """
                insert into people (id, name, team, role, github_login, slack_handle, slack_user_id)
                values (%s, %s, %s, %s, %s, %s, %s)
                on conflict (id) do update set
                    name = excluded.name, team = excluded.team, role = excluded.role,
                    github_login = excluded.github_login, slack_handle = excluded.slack_handle,
                    slack_user_id = excluded.slack_user_id
                """,
                (p.id, p.name, p.team, p.role, p.github_login, p.slack_handle, p.slack_user_id),
            )
        for p in org.people:
            conn.execute("update people set manager_id = %s where id = %s", (p.manager, p.id))
        for topic_id, name in TOPICS.items():
            conn.execute(
                "insert into topics (id, name) values (%s, %s) on conflict (id) do update set name = excluded.name",
                (topic_id, name),
            )
    print(f"loaded {len(org.people)} people, {len(TOPICS)} topics")


if __name__ == "__main__":
    main()
