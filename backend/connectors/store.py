"""Writes normalized Artifacts and Events to the DB. Source-agnostic: every connector uses this."""

from schema import Artifact, Event
from topics import topics_for_paths


def store(conn, artifacts: list[Artifact], events: list[Event]) -> None:
    with conn.cursor() as cur:
        cur.executemany(
            """
            insert into artifacts (id, source, kind, title, text, url, timestamp)
            values (%s, %s, %s, %s, %s, %s, %s)
            on conflict (id) do update set
                title = excluded.title, text = excluded.text, url = excluded.url,
                timestamp = excluded.timestamp,
                -- text changed: force re-embedding
                embedding = case when artifacts.text = excluded.text then artifacts.embedding end
            """,
            [(a.id, a.source, a.kind, a.title, a.text, a.url, a.timestamp) for a in artifacts],
        )
        topic_rows = [
            (a.id, t) for a in artifacts for t in (set(a.topics) or topics_for_paths(a.paths))
        ]
        cur.executemany(
            "delete from artifact_topics where artifact_id = %s", [(a.id,) for a in artifacts]
        )
        cur.executemany(
            "insert into artifact_topics (artifact_id, topic_id) values (%s, %s) on conflict do nothing",
            topic_rows,
        )
        cur.executemany(
            "insert into sync_log (source, synced_at) values (%s, now()) "
            "on conflict (source) do update set synced_at = now()",
            [(src,) for src in {a.source for a in artifacts}],
        )
        cur.executemany(
            """
            insert into events (source, type, person_id, artifact_id, paths, timestamp, url)
            values (%s, %s, %s, %s, %s, %s, %s)
            on conflict (type, person_id, artifact_id) do update set
                timestamp = excluded.timestamp, paths = excluded.paths, url = excluded.url
            """,
            [(e.source, e.type, e.person_id, e.artifact_id, e.paths, e.timestamp, e.url) for e in events],
        )
