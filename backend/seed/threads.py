"""Seeded Slack-style Q&A threads.

Code decides who asks and who answers (so Slack agrees with GitHub on who the experts are and
the demo ranking stays stable); the LLM only writes the words, grounded in real PRs from the
topic. Everything here is pure; scripts/seed.py does the DB and LLM calls.
"""

import json
import random
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from schema import Artifact, Event, Person
from topics import TOPICS

# ~295 generated + the hand-written golden threads = ~300
QUOTAS = {
    "messaging": 35, "workflow": 35, "metadata": 35, "frontend": 30, "auth": 25, "billing": 25,
    "calendar": 20, "file-storage": 20, "message-queue": 20, "deploys": 25, "on-call": 25,
}
CHANNELS = {"deploys": "deploys", "on-call": "oncall"}  # everything else goes to #help
BATCH = 10
ANSWER_POOL = 4
SECOND_ANSWER_RATE = 0.3
DAYS_BACK = 175
# The Head of Eng shows up in every topic's GitHub data but rarely answers #help himself
BUSY_ANSWERER_DAMPING = {"victor-hale": 0.35}
# Non-code topics have no GitHub owners; these are fixed
FIXED_POOLS = {
    "deploys": {"ben-carter": 0.4, "jordan-blake": 0.3, "sam-patel": 0.2, "victor-hale": 0.1},
    "on-call": {"sam-patel": 0.4, "jordan-blake": 0.4, "daniel-novak": 0.2},
}
# Shared facts so generated ops threads agree with each other
OPS_FACTS = """Acme ops facts (use these, don't contradict them):
- Merging to main auto-deploys to staging. Production deploys go out on the Tuesday and Thursday release train, run by the release manager, via "Promote to production" in the deploy dashboard.
- Hotfixes: open a PR with the `hotfix` label, get one approval, then ask in #deploys for an off-train promote.
- Rollback is the "Roll back" button on the last release in the deploy dashboard; database migrations run before the new version boots, so a rollback with a migration needs an SRE.
- Feature flags are per workspace and can be flipped without a deploy.
- On-call is a weekly rotation between the SREs, handed over Monday 10:00. Alerts come from Sentry and the queue-backlog monitor (BullMQ on Redis) and page through PagerDuty.
- Runbooks live on the "Runbooks" page in the wiki. Incidents get a channel named #inc-<date>-<short-name> and a write-up within 2 working days."""

GOLDEN_IDS: set[str] = set()  # filled by seed.golden to keep generated ids from colliding


@dataclass
class ThreadPlan:
    id: str
    topic: str
    channel: str
    asker: str
    answerers: list[str]
    start: datetime
    context_prs: list[dict] = field(default_factory=list)  # [{number, title, summary}]


# ---- planning ----

def answer_weights(topic: str, github_scores: dict[str, float]) -> dict[str, float]:
    """Who answers questions on this topic, and how often (weights sum to 1)."""
    if topic in FIXED_POOLS:
        return FIXED_POOLS[topic]
    top = sorted(github_scores.items(), key=lambda kv: -kv[1])[:ANSWER_POOL]
    damped = {p: s * BUSY_ANSWERER_DAMPING.get(p, 1.0) for p, s in top}
    total = sum(damped.values()) or 1
    return {p: s / total for p, s in damped.items()}


def _asker_weight(p: Person) -> float:
    if "Manager" in p.role or p.role.startswith("Head"):
        return 0.3
    return 2.0 if p.role in ("Software Engineer", "Product Manager", "Design Engineer") else 1.0


def _work_time(rng: random.Random, now: datetime) -> datetime:
    """A random weekday working-hours moment in the last DAYS_BACK days (Pacific, UTC-7)."""
    while True:
        day = (now - timedelta(days=rng.randint(1, DAYS_BACK))).date()
        if day.weekday() < 5:
            break
    local = datetime(day.year, day.month, day.day, rng.randint(9, 16), rng.randint(0, 59), tzinfo=UTC)
    return local + timedelta(hours=7)


def _ids(n: int):
    i = 0
    while n:
        i += 1
        id_ = f"seed-thread-{i:04d}"
        if id_ not in GOLDEN_IDS:
            n -= 1
            yield id_


def plan_threads(github_scores_by_topic: dict[str, dict[str, float]], people: list[Person],
                 now: datetime, rng: random.Random, exclude_askers: set[str] = frozenset()) -> list[ThreadPlan]:
    ids = _ids(sum(QUOTAS.values()))
    plans = []
    for topic, n in QUOTAS.items():
        weights = answer_weights(topic, github_scores_by_topic.get(topic, {}))
        pool, w = list(weights), list(weights.values())
        if not pool:
            continue  # nobody has GitHub history here; no one to answer
        for _ in range(n):
            first = rng.choices(pool, w)[0]
            answerers = [first]
            others = [p for p in pool if p != first]
            if others and rng.random() < SECOND_ANSWER_RATE:
                answerers.append(rng.choice(others))
            # Experts in this topic don't ask about it
            askers = [p for p in people if p.id not in weights and p.id not in exclude_askers]
            asker = rng.choices(askers, [_asker_weight(p) for p in askers])[0].id
            plans.append(ThreadPlan(next(ids), topic, CHANNELS.get(topic, "help"), asker, answerers,
                                    _work_time(rng, now)))
    return plans


def batches(plans: list[ThreadPlan]) -> list[list[ThreadPlan]]:
    out = []
    for topic in QUOTAS:
        same = [p for p in plans if p.topic == topic]
        out += [same[i : i + BATCH] for i in range(0, len(same), BATCH)]
    return out


# ---- prompting ----

SYSTEM = """You write realistic internal Slack threads for Acme, an engineering team building a CRM. \
Acme's codebase is the open-source Twenty CRM (NestJS + TypeORM + BullMQ server, React frontend).

Rules:
- Each thread: a question from a teammate, an answer from someone who knows the area, and sometimes a short follow-up from a second expert.
- Sound like real Slack: casual, specific, short. Questions 1 to 3 sentences, answers 2 to 6 sentences.
- Ground every technical claim in the context provided. When an answer relies on a PR, mention it as #NUMBER. Only use PR numbers from the context. Never invent PR numbers, file names you weren't given, or numbers.
- Never write any person's name, @handle, or email. Refer to people by role if needed ("the on-call SRE").
- Vary the questions: how something works, why something broke, where code lives, how to do a task.
- Reply with only JSON: {"threads": [{"question": "...", "answer": "...", "followup": "..." or null}, ...]}"""


def build_prompt(topic: str, batch: list[ThreadPlan], people: dict[str, Person]) -> str:
    lines = [f"Topic: {TOPICS[topic]}", ""]
    prs = batch[0].context_prs
    if prs:
        lines.append("Context PRs:")
        lines += [f"- #{p['number']} {p['title']}: {p['summary']}" for p in prs]
    else:
        lines.append(OPS_FACTS)
    lines += ["", f"Write exactly {len(batch)} threads, in this order:"]
    for i, plan in enumerate(batch, 1):
        roles = [people[a].role for a in plan.answerers]
        followup = f", follow-up from a {roles[1]}" if len(roles) > 1 else ", followup: null"
        lines.append(f"{i}. asked by a {people[plan.asker].role}, answered by a {roles[0]}{followup}")
    return "\n".join(lines)


# ---- parsing + validation ----

def parse_threads(raw: str, n: int) -> list[dict]:
    raw = re.sub(r"```(?:json)?", "", raw or "")
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end < start:
        raise ValueError("no JSON object in reply")
    try:
        threads = json.loads(raw[start : end + 1])["threads"]
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        raise ValueError(f"bad JSON: {e}") from e
    if not isinstance(threads, list) or len(threads) < n:
        raise ValueError(f"expected {n} threads, got {len(threads) if isinstance(threads, list) else 0}")
    out = []
    for t in threads[:n]:
        if not isinstance(t, dict) or not str(t.get("question") or "").strip() or not str(t.get("answer") or "").strip():
            raise ValueError("thread missing question or answer")
        out.append({k: (str(t[k]).strip() if t.get(k) else None) for k in ("question", "answer", "followup")})
    return out


_PR_REF = re.compile(r"#(\d{3,6})\b")


def scrub_pr_refs(text: str, allowed: set[str]) -> str:
    """Drop PR numbers the model made up."""
    def fix(m):
        return m.group(0) if m.group(1) in allowed else "a recent PR"
    return _PR_REF.sub(fix, text)


def leaked_names(text: str, people: list[Person]) -> list[str]:
    """Persona full names or real GitHub logins that shouldn't be in generated text."""
    found = []
    for p in people:
        for token in filter(None, [p.name, p.github_login]):
            if re.search(rf"\b{re.escape(token)}\b", text, re.I):
                found.append(token)
    return found


# ---- records ----

def to_records(plan: ThreadPlan, texts: dict, people: dict[str, Person]) -> tuple[Artifact, list[Event]]:
    """Turn a plan + generated text into the same Artifact/Event shapes the Slack connector emits."""
    allowed = {str(p["number"]) for p in plan.context_prs}
    rng = random.Random(plan.id)
    messages = [(plan.asker, plan.start, texts["question"])]
    t = plan.start + timedelta(minutes=rng.randint(4, 90))
    messages.append((plan.answerers[0], t, texts["answer"]))
    if len(plan.answerers) > 1 and texts.get("followup"):
        messages.append((plan.answerers[1], t + timedelta(minutes=rng.randint(5, 60)), texts["followup"]))
    messages = [(who, ts, scrub_pr_refs(msg, allowed)) for who, ts, msg in messages]
    return records_from_messages(plan.id, plan.channel, [plan.topic], messages, people)


def records_from_messages(thread_id: str, channel: str, topic_ids: list[str],
                          messages: list[tuple[str, datetime, str]], people: dict[str, Person],
                          ) -> tuple[Artifact, list[Event]]:
    text = "\n".join(f"{people[who].name}: {msg}" for who, _, msg in messages)
    question = " ".join(messages[0][2].split())
    title = f"#{channel}: {question[:80].rstrip()}{'...' if len(question) > 80 else ''}"
    url = f"/artifacts/{thread_id}"
    artifact = Artifact(id=thread_id, source="seed", kind="thread", title=title, text=text,
                        url=url, timestamp=messages[0][1], topics=topic_ids)
    asker = messages[0][0]
    events = [Event(source="seed", type="asked", person_id=asker, artifact_id=thread_id, text=text,
                    timestamp=messages[0][1], url=url, title=title)]
    answered = set()
    for who, ts, _ in messages[1:]:
        if who != asker and who not in answered:
            answered.add(who)
            events.append(Event(source="seed", type="answered", person_id=who, artifact_id=thread_id,
                                text=text, timestamp=ts, url=url, title=title))
    return artifact, events
