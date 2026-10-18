"""Run the demo questions once so their answers are in the LLM cache (instant on stage, and still
working if OpenRouter is down). Cleans up the pending actions it creates.

    uv run python -m scripts.warm_demo
"""

import os
import time

import db
from agent.chat import handle
from schema import ChatRequest
from seed.demo_questions import FOLLOW_UPS, QUESTIONS, USER, bubble_questions


def main() -> None:
    # Warming runs offline, so wait for slow answers instead of falling back (chat uses ~30s)
    os.environ["LLM_TIMEOUT"] = "180"
    created = []
    with db.connect() as conn:
        for question in QUESTIONS + bubble_questions():
            start = time.time()
            res = handle(conn, ChatRequest(message=question, user=USER))
            created += [a.id for a in res.pending_actions]
            for follow_up in FOLLOW_UPS if question == QUESTIONS[0] else []:
                more = handle(conn, ChatRequest(message=follow_up, user=USER, conversation_id=res.conversation_id))
                created += [a.id for a in more.pending_actions]
            cited = len(res.reply.citations)
            top = res.experts[0].name if res.experts else "nobody"
            label = question.splitlines()[-1] + (" (code bubble)" if question.startswith("About ") else "")
            print(f"  {time.time() - start:5.1f}s  {cited} citations, top: {top:14}  {label}")
        conn.execute("delete from pending_actions where id = any(%s)", (created,))
    print("cached. Run it again: every question should take about a second")


if __name__ == "__main__":
    main()
