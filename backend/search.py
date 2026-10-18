"""Vector search over artifacts. Backs search_knowledge and find_experts."""

from dataclasses import dataclass, field
from datetime import datetime

from embeddings import embed_query

SNIPPET_CHARS = 400


@dataclass
class Hit:
    id: str
    source: str
    title: str | None
    url: str
    timestamp: datetime
    similarity: float
    snippet: str
    topics: list[str] = field(default_factory=list)


def search_artifacts(conn, query: str, k: int = 20) -> list[Hit]:
    vec = embed_query(query)
    rows = conn.execute(
        """
        select a.id, a.source, a.title, a.url, a.timestamp, 1 - (a.embedding <=> %(v)s) as sim,
               left(a.text, %(n)s),
               coalesce(array_agg(t.topic_id) filter (where t.topic_id is not null), '{}')
        from artifacts a
        left join artifact_topics t on t.artifact_id = a.id
        where a.embedding is not null
        group by a.id
        order by a.embedding <=> %(v)s
        limit %(k)s
        """,
        {"v": vec, "k": k, "n": SNIPPET_CHARS},
    ).fetchall()
    return [Hit(*row) for row in rows]
