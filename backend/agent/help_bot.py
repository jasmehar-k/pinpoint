"""#help fast path: answer new questions in-thread with the cited answer and who knows this.

Pure pieces here; scripts/help_bot.py polls Slack every ~30s (no Events API, so no public URL).
"""

import re

from agent.chat import Answered
from graph.experts import topic_label
from schema import Citation, Person
from topics import TOPICS

GUEST = Person(id="slack-guest", name="A teammate", team="Acme", role="engineer", manager=None,
               github_login=None, slack_handle="guest")

_ASKING = re.compile(r"\b(how|why|what|who|where|when|which|anyone|anybody|know|help|stuck|issue|error|broken|fail\w*)\b", re.I)


def is_new_question(msg: dict, bot_user_id: str) -> bool:
    """A top-level human message that asks for something: a "?" or a question/help word anywhere
    ("hey, who's the best person for IMAP. needed some help" counts; "thanks!" doesn't)."""
    if msg.get("subtype") or msg.get("bot_id") or not msg.get("user") or msg["user"] == bot_user_id:
        return False
    if msg.get("thread_ts") and msg["thread_ts"] != msg["ts"]:
        return False  # a reply inside a thread
    text = (msg.get("text") or "").strip()
    return len(text) >= 12 and ("?" in text or bool(_ASKING.search(text)))


def _absolute(url: str, app_url: str) -> str:
    return f"{app_url.rstrip('/')}{url}" if url.startswith("/") else url


def slack_links(text: str, citations: list[Citation], app_url: str) -> str:
    """[1] -> a Slack link to that source. Seeded threads link into the Pinpoint app."""
    urls = {c.id: _absolute(c.url, app_url) for c in citations}
    return re.sub(r"\[(\d+)\]", lambda m: f"<{urls[m.group(1)]}|[{m.group(1)}]>" if m.group(1) in urls
                  else m.group(0), text)


def format_reply(a: Answered, app_url: str) -> str:
    """Layout follows frontend/mockups/2-4 (#help fast path)."""
    lines = [slack_links(a.text, a.citations, app_url)]
    if a.experts:
        topic = a.experts[0].topic
        area = topic_label(topic).lower() if topic in TOPICS else "this"
        lines += ["", f"*Who knows {area}*"]
        for e in a.experts:
            summary = e.evidence_summary[0].lower() + e.evidence_summary[1:]
            booked = f" · {e.availability.booked_pct:.0%} booked this week" if e.availability else ""
            tag = " · *best bet*" if e.badge == "recommended" else ""
            lines.append(f"*{e.name}* · {summary}{booked}{tag}")
    lines += ["", f"<{app_url}|Open in Pinpoint> to draft a DM or book time. "
                  "React :white_check_mark: if this answered it, and I'll save it for the next person who asks."]
    return "\n".join(lines)


# ---- "That answered it" ----

CHECKS = {"white_check_mark", "heavy_check_mark", "ballot_box_with_check"}
SAVED_NOTE = "Saved as a known answer. The next person who asks about this will be pointed here."


def answered_it(msg: dict, bot_user_id: str) -> bool:
    """A person (not the bot) reacted with a check mark."""
    return any(r.get("name") in CHECKS and any(u != bot_user_id for u in r.get("users", []))
               for r in msg.get("reactions") or [])


_SLACK_LINK = re.compile(r"<[^|>]+\|([^>]+)>")


def thread_text(messages: list[dict], people: dict, bot_user_id: str, clean) -> str:
    """The thread as "Name: message" lines, keeping only the answer part of Pinpoint's reply
    (its expert list goes stale; the answer doesn't)."""
    lines = []
    for m in messages:
        if m.get("subtype") and m.get("subtype") != "bot_message":
            continue
        text = m.get("text") or ""
        if m.get("bot_id") or m.get("user") == bot_user_id:
            if text.startswith(SAVED_NOTE[:20]):
                continue
            answer = _SLACK_LINK.sub(r"\1", text.split("\n\n")[0]).strip()
            lines.append(f"Pinpoint: {answer}")
        else:
            p = people.get(m.get("user"))
            lines.append(f"{p.name if p else 'Someone'}: {clean(text, people)}")
    return "\n".join(lines)
