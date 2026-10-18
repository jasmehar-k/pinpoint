"""#help fast path: answer new questions in-thread with the cited answer and who knows this.

Pure pieces here; scripts/help_bot.py polls Slack every ~30s (no Events API, so no public URL).
"""

import re

from agent.chat import Answered
from schema import Citation, Person

GUEST = Person(id="slack-guest", name="A teammate", team="Acme", role="engineer", manager=None,
               github_login=None, slack_handle="guest")

_QUESTION_START = re.compile(r"^(how|why|what|who|where|when|which|does|do|is|are|can|could|should|has|any(one)?)\b", re.I)


def is_new_question(msg: dict, bot_user_id: str) -> bool:
    """A top-level human message in the channel that reads like a question."""
    if msg.get("subtype") or msg.get("bot_id") or not msg.get("user") or msg["user"] == bot_user_id:
        return False
    if msg.get("thread_ts") and msg["thread_ts"] != msg["ts"]:
        return False  # a reply inside a thread
    text = (msg.get("text") or "").strip()
    return len(text) >= 12 and ("?" in text or bool(_QUESTION_START.search(text)))


def _absolute(url: str, app_url: str) -> str:
    return f"{app_url.rstrip('/')}{url}" if url.startswith("/") else url


def slack_links(text: str, citations: list[Citation], app_url: str) -> str:
    """[1] -> a Slack link to that source. Seeded threads link into the Pinpoint app."""
    urls = {c.id: _absolute(c.url, app_url) for c in citations}
    return re.sub(r"\[(\d+)\]", lambda m: f"<{urls[m.group(1)]}|[{m.group(1)}]>" if m.group(1) in urls
                  else m.group(0), text)


def format_reply(a: Answered, app_url: str) -> str:
    lines = [slack_links(a.text, a.citations, app_url)]
    if a.experts:
        lines += ["", "*Who knows this*"]
        for e in a.experts:
            summary = e.evidence_summary[0].lower() + e.evidence_summary[1:]
            booked = f" · {e.availability.booked_pct:.0%} booked this week" if e.availability else ""
            tag = " · *best bet*" if e.badge == "recommended" else ""
            lines.append(f"• *{e.name}* ({e.team}): {summary}{booked}{tag}")
    lines += ["", f"_Want a DM drafted or time booked? Ask in <{app_url}|Pinpoint>._"]
    return "\n".join(lines)
