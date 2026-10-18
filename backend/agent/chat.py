"""POST /chat. Three kinds of turns:

- question: search -> find_experts -> availability (code), then one LLM call writes the answer
  with citations and a DM draft. Code checks citations and names, writes the routing sentence,
  and creates a pending send_message action.
- schedule ("book time with him Wednesday"): mutual free slots -> pending schedule_meeting.
- redirect ("message Dana instead"): new DM draft to another expert from the last results.

Conversation state lives in memory; fine for a single-process demo.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

import llm
from agent import actions
from agent.compose import (SYSTEM, build_prompt, drop_unlisted_people, fallback_answer, fallback_dm,
                           intent, named_expert, parse_reply, pick_slot, renumber_citations,
                           routing_text, slot_label, slot_preference)
from graph.availability import get_availability
from graph.experts import apply_availability, find_experts, topic_label
from org import load_org, people_by_id
from schema import (ChatReply, ChatRequest, ChatResponse, Citation, Expert, ScheduleMeetingPayload,
                    SendMessagePayload)
from search import Hit, search_artifacts

ANSWER_SOURCES = 6
MAX_THREAD_SOURCES = 3  # keep real PRs in every answer; threads are discussion, PRs are ground truth
EXPERTS_SHOWN = 3


@dataclass
class Conversation:
    id: str
    user: str
    question: str = ""
    topic: str | None = None
    experts: list[Expert] = field(default_factory=list)
    contact: str | None = None  # who the last DM draft was for


CONVERSATIONS: dict[str, Conversation] = {}


def handle(conn, req: ChatRequest, now: datetime | None = None, client=None) -> ChatResponse:
    now = now or datetime.now(UTC)
    convo = CONVERSATIONS.get(req.conversation_id or "")
    if convo is None or convo.user != req.user:
        convo = Conversation(id=f"conv-{uuid.uuid4().hex[:8]}", user=req.user)
        CONVERSATIONS[convo.id] = convo

    kind = intent(req.message, convo.experts)
    if kind == "schedule":
        return _schedule(conn, convo, req.message, now)
    if kind == "redirect":
        return _redirect(conn, convo, req.message)
    return _question(conn, convo, req.message, now, client)


def _llm_answer(client, question, hits, asker, recipient) -> dict | None:
    client = client or llm.client()
    try:
        res = client.chat.completions.create(
            model=llm.model(), temperature=0.3, extra_body=llm.reasoning(),
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": build_prompt(question, hits, asker, recipient)}],
        )
        return parse_reply(res.choices[0].message.content)
    except Exception as e:  # rate limits, bad JSON, network: fall back to code-written text
        print(f"chat LLM call failed: {type(e).__name__}: {str(e)[:200]}")
        return None


def answer_sources(hits: list[Hit], n: int = ANSWER_SOURCES) -> list[Hit]:
    out, threads = [], 0
    for h in hits:
        is_thread = h.source != "github"
        if is_thread and threads >= MAX_THREAD_SOURCES:
            continue
        threads += is_thread
        out.append(h)
        if len(out) == n:
            break
    return out


def _citations(hits: list[Hit], order: list[int]) -> list[Citation]:
    return [Citation(id=str(n), title=hits[i].title or hits[i].id, url=hits[i].url, source=hits[i].source)
            for n, i in enumerate(order, 1)]


def _question(conn, convo: Conversation, question: str, now: datetime, client) -> ChatResponse:
    people = people_by_id()
    asker = people[convo.user]
    hits = answer_sources(search_artifacts(conn, question, k=ANSWER_SOURCES * 3))
    experts = find_experts(conn, question, asker_id=convo.user, now=now)
    if experts:
        avail = get_availability(conn, [e.person_id for e in experts], now)
        experts = apply_availability(experts, avail.people)[:EXPERTS_SHOWN]
    routing, contact = routing_text(experts)
    recipient = people[contact.person_id] if contact else None

    reply = _llm_answer(client, question, hits, asker, recipient)
    if reply:
        # The answer explains the code; who to ask is the routing sentence's job, so no names at all
        answer = drop_unlisted_people(reply["answer"], load_org().people, allowed=set())
        answer, order = renumber_citations(answer, len(hits))
        if not answer:
            answer, order = fallback_answer(hits)
    else:
        answer, order = fallback_answer(hits)

    convo.question, convo.experts = question, experts
    convo.topic = experts[0].topic if experts else None
    pending = []
    if recipient:
        dm = (reply or {}).get("dm") or ""
        dm = drop_unlisted_people(dm, load_org().people, {asker.id, recipient.id})
        if len(dm) < 40:
            dm = fallback_dm(asker, recipient, question, convo.topic)
        pending.append(actions.create(conn, "send_message", SendMessagePayload(to=recipient.id, text=dm), asker.id))
        convo.contact = recipient.id

    return ChatResponse(conversation_id=convo.id,
                        reply=ChatReply(text=f"{answer}\n\n{routing}", citations=_citations(hits, order)),
                        experts=experts, pending_actions=pending)


def _schedule(conn, convo: Conversation, message: str, now: datetime) -> ChatResponse:
    people = people_by_id()
    target = named_expert(message, convo.experts)
    target_id = target.person_id if target else convo.contact or convo.experts[0].person_id
    first = people[target_id].name.split()[0]
    attendees = [convo.user, target_id]
    avail = get_availability(conn, attendees, now)
    slot, exact = pick_slot(avail.mutual_free_slots, message)
    if slot is None:
        text = f"You and {first} have no shared free time left this week. Want me to message {first} instead?"
        return ChatResponse(conversation_id=convo.id, reply=ChatReply(text=text, citations=[]), availability=avail)

    asked_for_something = any(v is not None for v in slot_preference(message))
    lead = (f"You and {first} are both free {slot_label(slot)}." if exact or not asked_for_something
            else f"{first} isn't free then. The closest time you're both free is {slot_label(slot)}.")
    topic = topic_label(convo.topic) if convo.topic else "Intro"
    title = f"{topic} walkthrough ({people[convo.user].name.split()[0]} / {first})"
    action = actions.create(conn, "schedule_meeting",
                            ScheduleMeetingPayload(title=title, attendees=attendees, slot=slot), convo.user)
    text = f"{lead} I've drafted a 30-minute invite. Approve it and I'll add it to both calendars."
    return ChatResponse(conversation_id=convo.id, reply=ChatReply(text=text, citations=[]),
                        availability=avail, pending_actions=[action])


def _redirect(conn, convo: Conversation, message: str) -> ChatResponse:
    people = people_by_id()
    target = named_expert(message, convo.experts)
    asker, recipient = people[convo.user], people[target.person_id]
    dm = fallback_dm(asker, recipient, convo.question, convo.topic)
    action = actions.create(conn, "send_message", SendMessagePayload(to=recipient.id, text=dm), asker.id)
    convo.contact = recipient.id
    busy = target.badge == "busy" and target.availability
    note = f" Heads up: {recipient.name.split()[0]} is {target.availability.booked_pct:.0%} booked this week." if busy else ""
    text = f"Here's a draft to {recipient.name.split()[0]} instead.{note}"
    return ChatResponse(conversation_id=convo.id, reply=ChatReply(text=text, citations=[]),
                        experts=[target], pending_actions=[action])
