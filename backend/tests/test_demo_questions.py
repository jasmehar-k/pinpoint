import re

import config
from seed.demo_questions import QUESTIONS


def test_every_frontend_suggestion_is_warmed():
    """The answer cache matches exact text, so a reworded button means a slow, uncached answer."""
    demo_ts = (config.REPO_ROOT / "frontend" / "src" / "lib" / "demo.ts").read_text()
    block = demo_ts.split("SUGGESTED_QUESTIONS", 1)[1].split("];", 1)[0]
    suggestions = re.findall(r'"((?:[^"\\]|\\.)*)"', block)
    assert suggestions, "no SUGGESTED_QUESTIONS found in demo.ts"
    missing = [s for s in suggestions if s not in QUESTIONS]
    assert not missing, f"add these to seed/demo_questions.py: {missing}"


def test_bubble_questions_match_the_frontend_format():
    from seed.demo_questions import bubble_questions
    chip, selected = bubble_questions()
    path = "packages/twenty-server/src/modules/messaging/message-import-manager/crons/jobs/messaging-message-list-fetch.cron.job.ts"
    assert chip == f"About {path}:\n\nHow does this cron fit into inbound email sync?"
    assert selected.startswith(f"About {path}, lines 80-84:\n```\n            (messageChannel.webhookSubscriptionStatus !==\n")
    assert selected.endswith("\n```\n\nWhy does the cron skip channels with an active webhook?")


def test_page_topic_comes_from_the_file_path():
    from graph.experts import page_topic
    path = "packages/twenty-server/src/modules/messaging/message-import-manager/crons/jobs/x.ts"
    assert page_topic(f"About {path}, lines 80-84:\n```\ncode\n```\n\nWhat does this cron job do?") == "messaging"
    assert page_topic(f"About {path}:\n\nwhat is this") == "messaging"
    assert page_topic("How does inbound email sync work?") is None
