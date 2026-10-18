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

