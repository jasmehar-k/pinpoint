"""LLM topic tagging for artifacts that have no file paths (Slack threads).

One LLM call per batch of ~25 threads, never one per thread: free OpenRouter models are
rate-limited. Threads get short keys (t1, t2, ...) in the prompt so the model never has to
copy long artifact ids back. A batch that fails twice gets no topics; ingest never crashes.
"""

import json
import re
import time

import llm
from schema import Artifact
from topics import TOPICS

BATCH_SIZE = 25
THREAD_CHARS = 1500
MAX_TOPICS = 3

SYSTEM = (
    "You tag Slack threads from an engineering team with topics.\n"
    "Allowed topic ids:\n"
    + "\n".join(f"- {tid}: {label}" for tid, label in TOPICS.items())
    + "\n\nFor each thread give 1 to 3 topic ids from that list, or [] if none fit.\n"
    'Reply with only a JSON object mapping each thread key to a list, e.g. '
    '{"t1": ["messaging"], "t2": [], "t3": ["auth", "frontend"]}.'
)

# Accept ids or labels in any case ("Messaging (email sync)" -> "messaging")
_LOOKUP = {**{t.lower(): t for t in TOPICS}, **{label.lower(): t for t, label in TOPICS.items()}}


def parse_tags(raw: str, keys: list[str]) -> dict[str, list[str]]:
    """Parse the model's reply. Raises ValueError if there is no JSON object in it."""
    raw = re.sub(r"```(?:json)?", "", raw or "")
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end < start:
        raise ValueError("no JSON object in reply")
    try:
        data = json.loads(raw[start : end + 1])
    except json.JSONDecodeError as e:
        raise ValueError(f"bad JSON: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("reply is not a JSON object")

    tags = {}
    for key in keys:
        value = data.get(key) or []
        if isinstance(value, str):
            value = [value]
        topics = []
        for item in value if isinstance(value, list) else []:
            topic = _LOOKUP.get(str(item).strip().lower())
            if topic and topic not in topics:
                topics.append(topic)
        tags[key] = topics[:MAX_TOPICS]
    return tags


def _prompt(batch: list[Artifact]) -> str:
    threads = [{"key": f"t{i}", "text": a.text[:THREAD_CHARS]} for i, a in enumerate(batch, 1)]
    return json.dumps(threads, ensure_ascii=False)


def _tag_batch(batch: list[Artifact], client, model: str) -> dict[str, list[str]]:
    keys = [f"t{i}" for i in range(1, len(batch) + 1)]
    for attempt in (1, 2):
        try:
            res = client.chat.completions.create(
                model=model,
                temperature=0,
                messages=[{"role": "system", "content": SYSTEM},
                          {"role": "user", "content": _prompt(batch)}],
            )
            tags = parse_tags(res.choices[0].message.content, keys)
            return {a.id: tags[k] for a, k in zip(batch, keys)}
        except Exception as e:  # parse errors, rate limits, network: retry once, then give up
            print(f"  tagging batch failed (attempt {attempt}): {type(e).__name__}: {e}")
    print(f"  warning: {len(batch)} threads left without topics")
    return {a.id: [] for a in batch}


def reuse_tags(artifacts: list[Artifact], existing: dict[str, tuple[str, list[str]]],
               ) -> tuple[dict[str, list[str]], list[Artifact]]:
    """Split artifacts into (tags we can reuse, artifacts that still need the LLM).
    `existing` maps artifact id -> (stored text, stored topics). A thread keeps its old topics
    only if its text is unchanged and it had some, so reruns don't burn free-tier calls."""
    reused, todo = {}, []
    for a in artifacts:
        text, topics = existing.get(a.id, (None, []))
        if text == a.text and topics:
            reused[a.id] = topics
        else:
            todo.append(a)
    return reused, todo


def tag_topics(threads: list[Artifact], client=None, model: str | None = None,
               batch_size: int = BATCH_SIZE, pause: float = 3.0) -> dict[str, list[str]]:
    """artifact id -> 1 to 3 topic ids (or [] for "other")."""
    client = client or llm.client()
    model = model or llm.model()
    tags = {}
    for i in range(0, len(threads), batch_size):
        if i and pause:
            time.sleep(pause)
        tags.update(_tag_batch(threads[i : i + batch_size], client, model))
    return tags
