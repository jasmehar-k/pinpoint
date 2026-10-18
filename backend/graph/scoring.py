"""Expertise scoring. Dumb and explainable on purpose:

    score(person, topic) = sum over events of weight(type) * 0.5 ^ (age_days / 90)

Pure functions here; scripts/score.py writes the result to the `expertise` table.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from schema import EVENT_WEIGHTS

HALF_LIFE_DAYS = 90
EVIDENCE_PER_EDGE = 3


@dataclass(frozen=True)
class EventRow:
    person_id: str
    type: str
    artifact_id: str
    title: str
    url: str
    timestamp: datetime
    topic_id: str | None = None


@dataclass
class Edge:
    """One (person, topic) expertise edge with its receipts."""

    person_id: str
    topic_id: str
    score: float = 0.0
    counts: Counter = field(default_factory=Counter)
    evidence: list[tuple[float, EventRow]] = field(default_factory=list)
    last_active: datetime | None = None

    def top_evidence(self) -> list[EventRow]:
        return [e for _, e in sorted(self.evidence, key=lambda x: -x[0])[:EVIDENCE_PER_EDGE]]


def decay(ts: datetime, now: datetime) -> float:
    age_days = max((now - ts).total_seconds() / 86400, 0)
    return 0.5 ** (age_days / HALF_LIFE_DAYS)


def contribution(event_type: str, ts: datetime, now: datetime) -> float:
    return EVENT_WEIGHTS[event_type] * decay(ts, now)


def score_edges(rows: list[EventRow], now: datetime) -> dict[tuple[str, str], Edge]:
    """rows: one per (event, topic of its artifact). Events on untagged artifacts are skipped."""
    edges: dict[tuple[str, str], Edge] = {}
    for row in rows:
        if not row.topic_id:
            continue
        key = (row.person_id, row.topic_id)
        edge = edges.get(key) or edges.setdefault(key, Edge(row.person_id, row.topic_id))
        c = contribution(row.type, row.timestamp, now)
        edge.score += c
        edge.counts[row.type] += 1
        edge.evidence.append((c, row))
        if edge.last_active is None or row.timestamp > edge.last_active:
            edge.last_active = row.timestamp
    return edges


def rank_by_topic(edges: dict[tuple[str, str], Edge]) -> dict[str, list[Edge]]:
    by_topic = defaultdict(list)
    for edge in edges.values():
        by_topic[edge.topic_id].append(edge)
    return {t: sorted(es, key=lambda e: -e.score) for t, es in by_topic.items()}
