"""Generate the seeded Slack threads (~300) and load them. Rerunnable: LLM output is cached per
batch under backend/data/raw/seed/, keyed by the prompt, so reruns cost no LLM calls.

    uv run python -m scripts.seed
    then: scripts.embed, scripts.score, pytest -m demo
"""

import hashlib
import json
import random
import time
from collections import Counter
from datetime import UTC, datetime

import config
import db
import llm
from connectors.store import store
from graph.scoring import score_edges
from org import load_org
from scripts.score import load_rows
from seed.golden import golden_records
from seed.threads import (SYSTEM, batches, build_prompt, leaked_names, parse_threads, plan_threads,
                          to_records)

CACHE_DIR = config.BACKEND_ROOT / "data" / "raw" / "seed"
CONTEXT_PRS = 12
ATTEMPTS = 3
PAUSE = 3.0
SEED = 42


def github_scores(conn, now) -> dict[str, dict[str, float]]:
    rows = [r for r in load_rows(conn) if not r.artifact_id.startswith(("seed-", "slack:"))]
    out: dict[str, dict[str, float]] = {}
    for (person, topic), edge in score_edges(rows, now).items():
        out.setdefault(topic, {})[person] = edge.score
    return out


def topic_prs(conn, topic: str) -> list[dict]:
    rows = conn.execute(
        """
        select a.id, a.text from artifacts a join artifact_topics t on t.artifact_id = a.id
        where t.topic_id = %s and a.source = 'github' order by a.timestamp desc limit 80
        """,
        (topic,),
    ).fetchall()
    prs = []
    for id_, text in rows:
        title, _, body = text.partition("\n\n")
        prs.append({"number": int(id_.removeprefix("github:pr:")), "title": title,
                    "summary": " ".join(body.split())[:300]})
    return prs


def generate(prompt: str, n: int, people) -> list[dict] | None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256((SYSTEM + prompt).encode()).hexdigest()[:16]
    path = CACHE_DIR / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())
    for attempt in range(1, ATTEMPTS + 1):
        try:
            res = llm.client().chat.completions.create(
                model=llm.model(), temperature=0.8,
                messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
            )
            threads = parse_threads(res.choices[0].message.content, n)
            leaks = {name for t in threads for v in t.values() if v for name in leaked_names(v, people)}
            if leaks:
                raise ValueError(f"names leaked into text: {sorted(leaks)}")
            path.write_text(json.dumps(threads))
            return threads
        except Exception as e:
            print(f"    attempt {attempt} failed: {type(e).__name__}: {str(e)[:150]}")
            time.sleep(PAUSE * attempt * 3)
    return None


def main() -> None:
    now = datetime.now(UTC)
    org = load_org()
    people = {p.id: p for p in org.people}

    with db.connect(vector=False) as conn:
        plans = plan_threads(github_scores(conn, now), org.people, now, random.Random(SEED),
                             exclude_askers={"priya-shah"})
        prs = {t: topic_prs(conn, t) for t in {p.topic for p in plans}}

    records, skipped = golden_records(people, now), 0
    for i, batch in enumerate(batches(plans)):
        topic = batch[0].topic
        pool = prs.get(topic) or []
        if pool:
            offset = (i * CONTEXT_PRS) % len(pool)
            context = (pool[offset:] + pool[:offset])[:CONTEXT_PRS]
            for plan in batch:
                plan.context_prs = context
        print(f"  batch {i + 1}: {topic}, {len(batch)} threads")
        texts = generate(build_prompt(topic, batch, people), len(batch), org.people)
        if texts is None:
            skipped += len(batch)
            continue
        records += [to_records(plan, t, people) for plan, t in zip(batch, texts)]
        time.sleep(PAUSE)

    artifacts = [a for a, _ in records]
    events = [e for _, es in records for e in es]
    with db.connect(vector=False) as conn:
        conn.execute("delete from artifacts where source = 'seed'")  # events cascade
        store(conn, artifacts, events)

    print(f"stored {len(artifacts)} seeded threads ({skipped} skipped after {ATTEMPTS} failed attempts)")
    answers = Counter((a.topics[0], e.person_id) for a, es in records for e in es if e.type == "answered")
    for topic in sorted({t for t, _ in answers}):
        top = sorted(((n, p) for (t, p), n in answers.items() if t == topic), reverse=True)[:4]
        print(f"  {topic:14} " + ", ".join(f"{people[p].name} {n}" for n, p in top))


if __name__ == "__main__":
    main()
