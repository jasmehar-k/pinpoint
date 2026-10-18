"""find_experts: who knows about this question, with receipts.

Embed the question -> top artifacts -> credit the people on them by
similarity x type weight x decay. The question's topic is the one most of those artifacts
share; the evidence line comes from that topic's expertise row.
"""

import re
from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from graph.scoring import EventRow, contribution
from org import people_by_id
from schema import Evidence, Expert
from search import Hit, mentioned_prs, search_artifacts
from topics import TOPICS, topic_for_path

TOP_ARTIFACTS = 40
# Only credit artifacts close to the best match. Without this, 30 loosely related PRs outvote the
# 5 threads that actually answer the question (ops questions routed to the Head of Eng).
RELATIVE_CUTOFF = 0.10
NAMED_PR_WEIGHT = 5.0  # "what's PR 28080?": that PR counts 5x a top search match
MAX_EXPERTS = 5
# Mention "reviewed N of <top expert>'s PRs" only when it's a real pattern
REVIEWED_OF_MIN = 10


@dataclass
class Candidate:
    person_id: str
    score: float = 0.0
    evidence: list[tuple[float, EventRow]] = field(default_factory=list)

    def top_evidence(self, n: int = 3) -> list[Evidence]:
        seen, out = set(), []
        for _, e in sorted(self.evidence, key=lambda x: -x[0]):
            if e.artifact_id in seen:
                continue
            seen.add(e.artifact_id)
            out.append(Evidence(type=e.type, title=e.title, url=e.url, timestamp=e.timestamp))
            if len(out) == n:
                break
        return out


def named_topic(paths: list[str]) -> str | None:
    """The topic a named PR touches most, by changed files. Frontend is the catch-all, so a
    specific topic wins whenever the PR has one."""
    counts = Counter(t for p in paths if (t := topic_for_path(p)))
    specific = [(n, t) for t, n in counts.items() if t != "frontend"]
    if specific:
        return max(specific)[1]
    return "frontend" if counts else None


_PAGE_PATH = re.compile(r"^About (packages/\S+?)(?:, lines \d+-\d+)?:", re.M)


def page_topic(query: str) -> str | None:
    """Questions from the code bubble start "About <file path>": the file says what it's about."""
    m = _PAGE_PATH.search(query)
    return topic_for_path(m.group(1)) if m else None


def dominant_topic(hits: list[Hit]) -> str | None:
    weights = Counter()
    for h in hits:
        for t in h.topics:
            weights[t] += h.similarity
    return weights.most_common(1)[0][0] if weights else None


def rank_candidates(hits: list[Hit], events: list[EventRow], now: datetime,
                    exclude: set[str] = frozenset()) -> list[Candidate]:
    sim = {h.id: h.similarity for h in hits}
    out: dict[str, Candidate] = {}
    for e in events:
        if e.artifact_id not in sim or e.person_id in exclude:
            continue
        c = sim[e.artifact_id] * contribution(e.type, e.timestamp, now)
        cand = out.get(e.person_id) or out.setdefault(e.person_id, Candidate(e.person_id))
        cand.score += c
        cand.evidence.append((c, e))
    return sorted(out.values(), key=lambda c: -c.score)


def relevant(hits: list[Hit], cutoff: float = RELATIVE_CUTOFF) -> list[Hit]:
    """Hits within `cutoff` similarity of the best one (hits come sorted best first)."""
    return [h for h in hits if h.similarity >= hits[0].similarity - cutoff] if hits else []


CORRECTION_FACTOR = 0.5  # each "not the right person" halves that person's score on the topic


def apply_corrections(ranked: list[Candidate], corrections: list[tuple[str, str, str | None]],
                      not_experts: set[str] = frozenset()) -> list[Candidate]:
    """corrections: (expert_id, kind, redirect_to) for the question's topic. Every correction
    demotes the expert; a redirect also puts redirect_to in the list with at least the demoted
    expert's original score."""
    by_id = {c.person_id: c for c in ranked}
    original = {pid: c.score for pid, c in by_id.items()}
    for expert_id, kind, redirect_to in corrections:
        if expert_id in by_id:
            by_id[expert_id].score *= CORRECTION_FACTOR
        if kind == "redirect" and redirect_to and redirect_to not in not_experts:
            floor = original.get(expert_id, 0.0)
            target = by_id.get(redirect_to) or by_id.setdefault(redirect_to, Candidate(redirect_to))
            target.score = max(target.score, floor)
    return sorted(by_id.values(), key=lambda c: -c.score)


def topic_label(topic_id: str) -> str:
    return TOPICS[topic_id].split(" (")[0]


def _ago(ts: datetime | None, now: datetime) -> str | None:
    if ts is None:
        return None
    days = (now - ts).days
    return "active today" if days <= 0 else "active 1 day ago" if days == 1 else f"active {days} days ago"


def evidence_summary(counts: dict, topic_id: str | None, last_active: datetime | None,
                     now: datetime, reviewed_of: tuple[str, int] | None = None) -> str:
    """e.g. "Reviewed 38 of Dana's Messaging PRs, authored 20 PRs in Messaging, active 2 days ago"."""
    label = topic_label(topic_id) if topic_id else None
    parts = []
    if reviewed_of and label:
        parts.append(f"Reviewed {reviewed_of[1]} of {reviewed_of[0]}'s {label} PRs")
    if n := counts.get("authored"):
        parts.append(f"authored {n} PR{'s' * (n != 1)} in {label}" if label else f"authored {n} related PRs")
    if (n := counts.get("reviewed")) and not reviewed_of:
        parts.append(f"reviewed {n}")
    if n := counts.get("answered"):
        parts.append(f"answered {n} question{'s' * (n != 1)}")
    if ago := _ago(last_active, now):
        parts.append(ago)
    text = ", ".join(parts) or "Related activity"
    return text[0].upper() + text[1:]


# ---- DB layer ----

def _events_on(conn, artifact_ids: list[str]) -> list[EventRow]:
    rows = conn.execute(
        """
        select e.person_id, e.type, e.artifact_id, coalesce(a.title, a.id), e.url, e.timestamp
        from events e join artifacts a on a.id = e.artifact_id
        where e.artifact_id = any(%s)
        """,
        (artifact_ids,),
    ).fetchall()
    return [EventRow(*r) for r in rows]


def _edge_counts(conn, person_ids: list[str], topic_id: str | None) -> dict[str, dict]:
    if not topic_id:
        return {}
    rows = conn.execute(
        "select person_id, counts from expertise where topic_id = %s and person_id = any(%s)",
        (topic_id, person_ids),
    ).fetchall()
    return dict(rows)


def _last_active(conn, person_ids: list[str]) -> dict[str, datetime]:
    rows = conn.execute(
        "select person_id, max(timestamp) from events where person_id = any(%s) group by 1",
        (person_ids,),
    ).fetchall()
    return dict(rows)


def _paths(conn, artifact_id: str) -> list[str]:
    row = conn.execute("select paths from events where artifact_id = %s and paths <> '{}' limit 1",
                       (artifact_id,)).fetchone()
    return row[0] if row else []


def _corrections(conn, topic_id: str) -> list[tuple[str, str, str | None]]:
    return conn.execute("select expert_id, kind, redirect_to from corrections where topic_id = %s",
                        (topic_id,)).fetchall()


def _reviewed_of(conn, author_id: str, reviewer_ids: list[str], topic_id: str) -> dict[str, int]:
    """How many of the author's PRs in this topic each reviewer reviewed."""
    rows = conn.execute(
        """
        select r.person_id, count(*)
        from events a
        join events r on r.artifact_id = a.artifact_id and r.type = 'reviewed'
        join artifact_topics t on t.artifact_id = a.artifact_id and t.topic_id = %s
        where a.type = 'authored' and a.person_id = %s and r.person_id = any(%s)
        group by 1
        """,
        (topic_id, author_id, reviewer_ids),
    ).fetchall()
    return dict(rows)


def find_experts(conn, query: str, asker_id: str | None = None, now: datetime | None = None,
                 limit: int = MAX_EXPERTS, exclude: tuple[str, ...] = ()) -> list[Expert]:
    now = now or datetime.now(UTC)
    people = people_by_id()
    # A PR the question names outweighs everything search found: its author and reviewers are who to ask
    named = [replace(h, similarity=NAMED_PR_WEIGHT) for h in mentioned_prs(conn, query) if h.id not in exclude]
    hits = named + [h for h in relevant(search_artifacts(conn, query, k=TOP_ARTIFACTS, exclude=exclude))
                    if h.id not in {n.id for n in named}]
    not_experts = {asker_id} if asker_id else set()
    topic = (named_topic(_paths(conn, named[0].id)) if named else None) or page_topic(query) or dominant_topic(hits)
    ranked = rank_candidates(hits, _events_on(conn, [h.id for h in hits]), now, not_experts)
    if topic:
        ranked = apply_corrections(ranked, _corrections(conn, topic), not_experts)
    ranked = ranked[:limit]
    if not ranked:
        return []

    ids = [c.person_id for c in ranked]
    counts = _edge_counts(conn, ids, topic)
    active = _last_active(conn, ids)
    top = ranked[0].person_id
    reviewed = _reviewed_of(conn, top, ids[1:], topic) if topic else {}
    asker_team = people[asker_id].team if asker_id in people else None

    experts = []
    for c in ranked:
        p = people[c.person_id]
        n = reviewed.get(c.person_id, 0)
        reviewed_of = (people[top].name.split()[0], n) if n >= REVIEWED_OF_MIN else None
        experts.append(Expert(
            person_id=p.id, name=p.name, team=p.team, role=p.role, topic=topic or "other",
            expertise=round(c.score, 2), rank_score=round(c.score, 2),
            evidence_summary=evidence_summary(counts.get(p.id, {}), topic, active.get(p.id), now, reviewed_of),
            evidence=c.top_evidence(), same_team=p.team == asker_team,
        ))
    return experts


# ---- availability ----

BUSY_AT = 0.70
SAME_TEAM_BOOST = 1.1  # "prefer your own team when scores are close"


def apply_availability(experts: list[Expert], people: list) -> list[Expert]:
    """Final rank = expertise x availability factor (x 1.1 for the asker's team).
    Badges: busy at 70%+ booked; the best-ranked expert who isn't busy is recommended."""
    by_id = {a.person_id: a for a in people}
    out = []
    for e in experts:
        a = by_id.get(e.person_id)
        f = a.factor if a else 1.0
        rank = e.expertise * f * (SAME_TEAM_BOOST if e.same_team else 1.0)
        badge = "busy" if a and a.booked_pct >= BUSY_AT else None
        out.append(e.model_copy(update={"availability": a, "rank_score": round(rank, 2), "badge": badge}))
    out.sort(key=lambda e: -e.rank_score)
    for e in out:
        if e.badge is None:
            e.badge = "recommended"
            break
    return out
