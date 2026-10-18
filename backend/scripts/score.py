"""Recompute the expertise table from events. Rerun after any ingest or seed step.

    uv run python -m scripts.score
"""

import json
from datetime import UTC, datetime

import db
from graph.scoring import EventRow, rank_by_topic, score_edges
from org import people_by_id


def load_rows(conn) -> list[EventRow]:
    rows = conn.execute(
        """
        select e.person_id, e.type, e.artifact_id, coalesce(a.title, a.id), e.url, e.timestamp, t.topic_id
        from events e
        join artifacts a on a.id = e.artifact_id
        left join artifact_topics t on t.artifact_id = e.artifact_id
        """
    ).fetchall()
    return [EventRow(*r) for r in rows]


def main() -> None:
    now = datetime.now(UTC)
    with db.connect(vector=False) as conn:
        edges = score_edges(load_rows(conn), now)
        with conn.cursor() as cur:
            cur.execute("delete from expertise")
            cur.executemany(
                """
                insert into expertise (person_id, topic_id, score, counts, evidence, last_active)
                values (%s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        e.person_id, e.topic_id, e.score, json.dumps(dict(e.counts)),
                        json.dumps([
                            {"type": r.type, "title": r.title, "url": r.url, "timestamp": r.timestamp.isoformat()}
                            for r in e.top_evidence()
                        ]),
                        e.last_active,
                    )
                    for e in edges.values()
                ],
            )

    names = people_by_id()
    print(f"scored {len(edges)} person-topic edges")
    for topic, ranked in sorted(rank_by_topic(edges).items()):
        top = ", ".join(f"{names[e.person_id].name} {e.score:.1f}" for e in ranked[:3])
        print(f"  {topic:14} {top}")


if __name__ == "__main__":
    main()
