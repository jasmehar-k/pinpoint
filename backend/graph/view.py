"""GET /graph: people, topics and expertise edges, plus bus factor per topic.

An expert on a topic scores at least THRESHOLD x that topic's top score (relative, because top
scores range from ~7 on Deploys to ~350 on Frontend). Bus factor = how many experts a topic has.
"""

from datetime import datetime

from graph.availability import get_availability
from graph.experts import evidence_summary
from org import load_org
from schema import GraphEdge, GraphPerson, GraphResponse, GraphTopic
from topics import TOPICS

THRESHOLD = 0.6
MIN_SCORE = 1.0  # below this nobody counts, however the topic's top compares
EDGES_PER_TOPIC = 6  # people + topics only, and few edges each: avoid the hairball


def bus_factor(scores: list[tuple[str, float]], threshold: float = THRESHOLD) -> tuple[list[str], str | None]:
    """(experts best first, next closest below the line) from (person, score) pairs."""
    ranked = sorted(scores, key=lambda x: -x[1])
    if not ranked:
        return [], None
    line = max(ranked[0][1] * threshold, MIN_SCORE)
    experts = [p for p, s in ranked if s >= line]
    below = [p for p, s in ranked if s < line]
    return experts, below[0] if below else None


def build_graph(conn, now: datetime) -> GraphResponse:
    people = load_org().people
    rows = conn.execute(
        "select person_id, topic_id, score, counts, last_active from expertise order by score desc"
    ).fetchall()
    by_topic: dict[str, list] = {t: [] for t in TOPICS}
    for row in rows:
        by_topic.setdefault(row[1], []).append(row)

    topics, edges = [], []
    for topic_id, label in TOPICS.items():
        topic_rows = by_topic.get(topic_id, [])
        experts, next_closest = bus_factor([(r[0], r[2]) for r in topic_rows])
        topics.append(GraphTopic(id=topic_id, name=label, experts=experts, bus_factor=len(experts),
                                 next_closest=next_closest))
        for person_id, _, score, counts, last_active in topic_rows[:max(EDGES_PER_TOPIC, len(experts))]:
            edges.append(GraphEdge(person_id=person_id, topic_id=topic_id, score=round(score, 2),
                                   evidence_summary=evidence_summary(counts, topic_id, last_active, now)))

    booked = {a.person_id: a.booked_pct for a in get_availability(conn, [p.id for p in people], now).people}
    return GraphResponse(
        threshold=THRESHOLD, topics=topics, edges=edges,
        people=[GraphPerson(person_id=p.id, name=p.name, team=p.team, booked_pct=booked.get(p.id, 0.0))
                for p in people],
    )
