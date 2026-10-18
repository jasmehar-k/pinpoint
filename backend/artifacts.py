"""GET /artifacts/{id}: one PR or thread with its people, for the artifact page."""

from org import load_org
from schema import ArtifactPerson, ArtifactResponse, ThreadMessage

UNKNOWN = "Someone"  # what the Slack connector writes for posters not in people.json


def parse_thread_text(text: str, names: dict[str, str]) -> list[ThreadMessage]:
    """Split stored thread text ("Name: message" lines) back into messages.
    A line that doesn't start with a known name continues the previous message."""
    messages: list[ThreadMessage] = []
    for line in text.split("\n"):
        name, sep, rest = line.partition(": ")
        if sep and (name in names or name == UNKNOWN):
            messages.append(ThreadMessage(person_id=names.get(name), name=name, text=rest))
        elif messages:
            messages[-1].text += "\n" + line
    return messages


def get_artifact(conn, artifact_id: str) -> ArtifactResponse | None:
    row = conn.execute(
        """
        select a.id, a.source, a.kind, a.title, a.url, a.timestamp, a.text,
               coalesce(array_agg(t.topic_id) filter (where t.topic_id is not null), '{}')
        from artifacts a left join artifact_topics t on t.artifact_id = a.id
        where a.id = %s group by a.id
        """,
        (artifact_id,),
    ).fetchone()
    if row is None:
        return None
    id_, source, kind, title, url, ts, text, topics = row
    people = {p.id: p for p in load_org().people}
    events = conn.execute(
        "select person_id, type from events where artifact_id = %s order by timestamp", (artifact_id,)
    ).fetchall()
    names = {p.name: p.id for p in people.values()}
    return ArtifactResponse(
        id=id_, source=source, kind=kind, title=title, url=url, timestamp=ts, topics=list(topics), text=text,
        messages=parse_thread_text(text, names) if kind == "thread" else None,
        people=[ArtifactPerson(person_id=pid, name=people[pid].name, type=t) for pid, t in events if pid in people],
    )
