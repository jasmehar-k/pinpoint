"""The questions we'll ask on stage. scripts/warm_demo runs them so their answers are cached.
The cache matches exact text, so this must include every suggested question in
frontend/src/lib/demo.ts, worded identically (tests/test_demo_questions.py checks)."""

import json
import re

import config

USER = "priya-shah"

QUESTIONS = [
    # the frontend's suggestion buttons, word for word
    "How does inbound email sync work?",
    "How are subscriptions and plan upgrades billed?",
    "How do workflow triggers and actions run?",
    "Why does my Gmail mailbox import keep failing?",
    # typed during the demo
    "How do I ship a hotfix before the release train?",
    "Why would an IMAP mailbox sync but import nothing?",
    # posted in #help during the demo; the bot answers it in-thread
    "who's the best person to ask about IMAP sync? new here",
]

FOLLOW_UPS = [
    "can you book time with Marcus on Wednesday at 10:30am?",
]


# ---- the /code page's bubble ----
# The bubble sends the page context in the message text (frontend/src/lib/pageContext.ts,
# withPageContext). Built from the frontend's own file so the cached text always matches.

CODE_FILE_TS = config.REPO_ROOT / "frontend" / "src" / "lib" / "code" / "messagingListFetchCron.ts"


def _code_file() -> tuple[str, list[str]]:
    ts = CODE_FILE_TS.read_text()
    path = re.search(r'\bpath: "([^"]+)"', ts).group(1)
    source = json.loads(re.search(r'\bsource: ("(?:[^"\\]|\\.)*")', ts).group(1))
    return path, re.sub(r"\n$", "", source).split("\n")


def with_page_context(question: str, path: str, lines: list[str] | None = None, start: int = 0) -> str:
    """Python twin of withPageContext."""
    if lines is None:
        return f"About {path}:\n\n{question}"
    end = start + len(lines) - 1
    return f"About {path}, lines {start}-{end}:\n```\n" + "\n".join(lines) + f"\n```\n\n{question}"


def bubble_questions() -> list[str]:
    if not CODE_FILE_TS.exists():
        return []
    path, source = _code_file()
    return [
        # the bubble's suggestion chip, nothing selected
        with_page_context("How does this cron fit into inbound email sync?", path),
        # demo.md spare beat: lines 80-84 selected
        with_page_context("Why does the cron skip channels with an active webhook?", path, source[79:84], 80),
    ]
