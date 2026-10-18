"""The questions we'll ask on stage. scripts/warm_demo runs them so their answers are cached.
The cache matches exact text, so this must include every suggested question in
frontend/src/lib/demo.ts, worded identically (tests/test_demo_questions.py checks)."""

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
