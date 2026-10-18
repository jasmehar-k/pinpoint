"""Pure pieces of the chat agent: intents, slot choice, LLM output checks, and the routing
sentence. The LLM writes the technical answer and the DM draft; code writes anything that names
people or times, so the agent can't invent an expert or a free slot."""

import json
import re
from datetime import time

from graph.availability import TZ
from schema import Expert, Person, Slot
from search import Hit
from topics import TOPICS

# ---- intents ----

_SCHEDULE = re.compile(
    r"\b(book|schedule|find (a |some )?time|set up (a |some )?(call|meeting|time|chat)|grab (some )?time|"
    r"meet (with|up)|put (something|time) on)\b", re.I)
_REDIRECT = re.compile(r"\b(message|dm|ping|ask|reach out to|draft (a message )?(to|for)|write to)\b", re.I)


def named_expert(message: str, experts: list[Expert]) -> Expert | None:
    """An expert from the last results whose first or full name appears in the message."""
    for e in experts:
        first = e.name.split()[0]
        if re.search(rf"\b({re.escape(e.name)}|{re.escape(first)})\b", message, re.I):
            return e
    return None


def intent(message: str, experts: list[Expert]) -> str:
    """'schedule', 'redirect' (draft a DM to someone else from the results), or 'question'."""
    if not experts:
        return "question"
    if _SCHEDULE.search(message):
        return "schedule"
    if _REDIRECT.search(message) and named_expert(message, experts):
        return "redirect"
    return "question"


# ---- slots ----

_DAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4}
_TIME = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", re.I)


def slot_preference(message: str) -> tuple[int | None, time | None, str | None]:
    """(weekday, time, 'morning'|'afternoon') from things like "Wednesday at 10:30am"."""
    text = message.lower()
    day = next((d for k, d in _DAYS.items() if re.search(rf"\b{k}", text)), None)
    part = "morning" if "morning" in text else "afternoon" if "afternoon" in text else None
    at = None
    for m in _TIME.finditer(text):
        hour, minute, ampm = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").lower()
        if not (m.group(2) or ampm) or hour > 12:
            continue  # a bare number like "30 minutes" isn't a time
        if ampm == "pm" and hour < 12:
            hour += 12
        if not ampm and hour < 8:
            hour += 12  # "at 2" during the workday means 2pm
        at = time(hour, minute)
        break
    return day, at, part


def pick_slot(slots: list[Slot], message: str) -> tuple[Slot | None, bool]:
    """Best slot for the request, and whether it matches what was asked for exactly."""
    if not slots:
        return None, False
    day, at, part = slot_preference(message)

    def local(s):
        return s.start.astimezone(TZ)

    def ok(s, use_time=True):
        t = local(s)
        if day is not None and t.weekday() != day:
            return False
        if use_time and at and t.time() != at:
            return False
        if part == "morning" and t.hour >= 12 or part == "afternoon" and t.hour < 12:
            return False
        return True

    exact = [s for s in slots if ok(s)]
    if exact:
        return exact[0], day is not None or at is not None or part is not None
    same_day = [s for s in slots if ok(s, use_time=False)]
    if same_day and at:  # asked for a time that's taken: nearest slot that day
        target = at.hour * 60 + at.minute
        return min(same_day, key=lambda s: abs(local(s).hour * 60 + local(s).minute - target)), False
    return slots[0], False


def slot_label(slot: Slot) -> str:
    t = slot.start.astimezone(TZ)
    return t.strftime("%a %-I:%M %p").replace(":00 ", " ")  # "Wed 10:30 AM", "Thu 2 PM"


# ---- LLM output ----

SYSTEM = """You help a new engineer understand a codebase, using only the numbered sources given \
(merged PRs and Slack threads from the team).

Reply with only JSON: {"answer": "...", "dm": "..."}

answer: 2 to 5 sentences answering the question from the sources, written like a friendly senior \
teammate on Slack: plain words, short sentences, no filler ("Additionally", "It is important to \
note"). Every sentence must end with at least one source number in square brackets, like [1] or [2][3]; leave out anything you can't cite. When you \
mention a PR number, cite the source that is that PR. PR sources are merged code changes and are \
the most reliable; THREAD sources are team discussions. Base the answer on PRs where they cover the \
question, and never name a class, function, file or event that isn't written in a source. If the \
question only asks who to talk to, give a short primer on the topic instead: what it is and what \
changed recently, from the sources. If the sources don't answer it, say so in one sentence. Never \
mention people, who replied, or "the thread", and don't recommend who to ask; that is handled \
separately.

dm: a short, friendly Slack message from the asker to the recipient. Open by introducing the asker \
in a few words using their role and team (for a new hire: "I'm Priya, new on Integrations"), then \
ask for 30 minutes this week to talk through the question. 2 to 4 sentences, first person, mention \
one relevant PR number from the sources (like #26180) if there is one. Use first names only, and no \
em dashes."""


def build_prompt(question: str, hits: list[Hit], asker: Person, recipient: Person | None) -> str:
    lines = ["Sources:"]
    for i, h in enumerate(hits, 1):
        kind = "PR" if h.source == "github" else "THREAD"
        lines.append(f"[{i}] ({kind}) {h.title}\n{' '.join(h.snippet.split())}")
    lines += ["", f"Question: {question}", "",
              f"Asker: {asker.name}, {asker.role} on {asker.team}."]
    lines.append(f"Recipient: {recipient.name}, {recipient.role} on {recipient.team}." if recipient
                 else "Recipient: none (leave dm empty).")
    return "\n".join(lines)


def parse_reply(raw: str) -> dict:
    raw = re.sub(r"```(?:json)?", "", raw or "")
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end < start:
        raise ValueError("no JSON object in reply")
    data = json.loads(raw[start : end + 1])
    if not isinstance(data, dict) or not str(data.get("answer") or "").strip():
        raise ValueError("reply has no answer")
    return {"answer": str(data["answer"]).strip(), "dm": str(data.get("dm") or "").strip()}


_PR_MENTION = re.compile(r"#(\d{3,6})\b")


def cite_mentioned_prs(answer: str, hits: list[Hit]) -> str:
    """Put the right [n] right after every PR number the answer mentions, when that PR is one of
    the sources, so "introduced in #26180" can't end up pointing at a different source."""
    index = {h.id.removeprefix("github:pr:"): i for i, h in enumerate(hits) if h.id.startswith("github:pr:")}

    def fix(m):
        i = index.get(m.group(1))
        if i is None:
            return m.group(0)
        marker = f"[{i + 1}]"
        rest = answer[m.end():m.end() + len(marker) + 1]
        return m.group(0) if marker in rest else f"{m.group(0)} {marker}"

    return _PR_MENTION.sub(fix, answer)


_MARKER = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def renumber_citations(text: str, n_sources: int) -> tuple[str, list[int]]:
    """Keep only [n] markers that point at a real source and renumber them 1, 2, 3 in order of
    first use. Returns the new text and the 0-based source indexes behind each new number."""
    order: list[int] = []

    def fix(m):
        out = []
        for part in m.group(1).split(","):
            i = int(part) - 1
            if 0 <= i < n_sources:
                if i not in order:
                    order.append(i)
                out.append(f"[{order.index(i) + 1}]")
        return "".join(out)

    text = _MARKER.sub(fix, text)
    text = re.sub(r"\]\s+\[", "][", text)  # "[1] [2]" -> "[1][2]"
    return re.sub(r"\s+([.,;])", r"\1", re.sub(r"[ \t]{2,}", " ", text)).strip(), order


def drop_unlisted_people(text: str, people: list[Person], allowed: set[str]) -> str:
    """Remove sentences that name a persona who isn't allowed in this text."""
    banned = [p.name for p in people if p.id not in allowed]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    kept = [s for s in sentences if not any(re.search(rf"\b{re.escape(n)}\b", s) for n in banned)]
    return " ".join(kept).strip()


def tidy_dm(text: str, recipient: Person) -> str:
    """First names only ("Hi Marcus", not "Hey Marcus Lee") and no em dashes."""
    text = text.replace(recipient.name, recipient.name.split()[0])
    text = re.sub(r"\s*[\u2014\u2013]\s*", ", ", text)
    return re.sub(r",\s*,", ",", text).strip()


_FULLWIDTH = re.compile(r"[\u3010\uff3b]\s*(\d+)\s*[\u3011\uff3d]")  # 【2】 ［2］
_MODEL_SOURCES = re.compile(r"\s*\(?\b[Ss]ources?:[^)\n]*\)?\s*$", re.M)  # "(Sources: 12)"
_TRAILING_MARKERS = re.compile(r"([.!?])\s*((?:\[\d+(?:\s*,\s*\d+)*\]\s*)+)")


def normalize_markers(text: str) -> str:
    """Bring the model's citation formats to plain [n] before anything else reads them:
    fullwidth brackets, its own "(Sources: ...)" (code adds one when needed), and markers placed
    after the period or on the next line ("ping.\n[1][2]" -> "ping [1][2].")."""
    text = _FULLWIDTH.sub(r"[\1]", text)
    text = _MODEL_SOURCES.sub("", text)
    text = _TRAILING_MARKERS.sub(lambda m: f" {m.group(2).strip()}{m.group(1)} ", text)
    return re.sub(r"[ \t]*\n+[ \t]*", " ", text).strip()


def drop_uncited(text: str) -> str:
    """Keep only sentences that cite a source. If nothing is cited at all, return the text as is;
    the caller attaches the top sources instead (the model forgot to cite rather than made it up)."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    cited = [s for s in sentences if _MARKER.search(s)]
    out = " ".join(cited) if cited else text
    return out if not out or out[-1] in ".!?)" else out + "."


def cite_top_sources(answer: str, n_sources: int, n: int = 2) -> tuple[str, list[int]]:
    """The model answered from the sources but forgot to cite: attach the best ones it was given."""
    order = list(range(min(n, n_sources)))
    return f"{answer} (Sources: {''.join(f'[{i + 1}]' for i in order)})", order


def fallback_answer(hits: list[Hit]) -> tuple[str, list[int]]:
    """When the LLM fails: point at the best sources instead of answering."""
    top = hits[:3]
    if not top:
        return "I couldn't find anything about this in our PRs or Slack threads yet.", []
    listed = "; ".join(f"{h.title} [{i}]" for i, h in enumerate(top, 1))
    return f"I couldn't write a summary just now, but these look most relevant: {listed}.", list(range(len(top)))


def fallback_dm(asker: Person, recipient: Person, question: str, topic: str | None) -> str:
    area = TOPICS[topic].split(" (")[0].lower() if topic in TOPICS else "this area"
    return (f"Hi {recipient.name.split()[0]}, I'm {asker.name.split()[0]}, I recently joined {asker.team}. "
            f"I'm getting up to speed on {area} and had a question: {question.strip()} "
            "Would you have 30 minutes this week to walk me through it? Thanks!")


# ---- routing sentence (code, not LLM) ----

def _clause(summary: str) -> str:
    first = summary.split(", ")[0]
    return first[0].lower() + first[1:]


def routing_text(experts: list[Expert]) -> tuple[str, Expert | None]:
    """Who to ask and why, from real numbers. Returns the text and the person to draft a DM to."""
    if not experts:
        return "I couldn't find anyone with history on this yet.", None
    top = max(experts, key=lambda e: e.expertise)
    rec = next((e for e in experts if e.badge == "recommended"), None)
    top_first = top.name.split()[0]

    def booked(e):
        return f"{e.availability.booked_pct:.0%} booked" if e.availability else "free"

    if rec is None:
        return (f"Everyone who knows this well is busy this week. {top_first} has the most context "
                f"({_clause(top.evidence_summary)}), so I drafted a message to {top_first} anyway."), top
    rec_first = rec.name.split()[0]
    if rec.person_id == top.person_id:
        return (f"{rec_first} knows this best ({_clause(rec.evidence_summary)}) and is {booked(rec)} this week, "
                f"so I drafted a message to {rec_first}."), rec
    team = ", is on your team," if rec.same_team else ""
    return (f"{top_first} knows this best but is {booked(top)} this week. {rec_first} "
            f"{_clause(rec.evidence_summary)}{team} and is {booked(rec)}, so I'd start with {rec_first}. "
            f"I drafted a message to {rec_first} below."), rec
