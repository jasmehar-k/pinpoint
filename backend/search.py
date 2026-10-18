"""Vector search over artifacts. Backs search_knowledge and find_experts."""

import re
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


def search_artifacts(conn, query: str, k: int = 20, exclude: tuple[str, ...] = ()) -> list[Hit]:
    """`exclude`: artifact ids to leave out, e.g. the thread being answered."""
    vec = embed_query(query)
    rows = conn.execute(
        """
        select a.id, a.source, a.title, a.url, a.timestamp, 1 - (a.embedding <=> %(v)s) as sim,
               left(a.text, %(n)s),
               coalesce(array_agg(t.topic_id) filter (where t.topic_id is not null), '{}')
        from artifacts a
        left join artifact_topics t on t.artifact_id = a.id
        where a.embedding is not null and a.id <> all(%(exclude)s)
        group by a.id
        order by a.embedding <=> %(v)s
        limit %(k)s
        """,
        {"v": vec, "k": k, "n": SNIPPET_CHARS, "exclude": list(exclude)},
    ).fetchall()
    return [Hit(*row) for row in rows]


_PR_REF = re.compile(r"(?:#|\bpr\s*#?|\bpull request\s*#?)(\d{3,6})\b", re.I)


def mentioned_prs(conn, question: str) -> list[Hit]:
    """PRs the question names ("what's PR 28080", "#26180"), as top hits. Vector search matches
    meaning, not numbers, so a named PR could otherwise be missed entirely."""
    ids = [f"github:pr:{n}" for n in dict.fromkeys(_PR_REF.findall(question))]
    if not ids:
        return []
    rows = conn.execute(
        """
        select a.id, a.source, a.title, a.url, a.timestamp, 1.0::float8, left(a.text, %(n)s),
               coalesce(array_agg(t.topic_id) filter (where t.topic_id is not null), '{}')
        from artifacts a left join artifact_topics t on t.artifact_id = a.id
        where a.id = any(%(ids)s) group by a.id
        """,
        {"ids": ids, "n": SNIPPET_CHARS},
    ).fetchall()
    found = {r[0]: Hit(*r) for r in rows}
    return [found[i] for i in ids if i in found]
