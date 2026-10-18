from agent.chat import Answered
from agent.help_bot import format_reply, is_new_question, slack_links
from schema import Availability, Citation, Expert

BOT = "UBOT"


def _msg(**kw):
    return {"ts": "100.1", "user": "U1", "text": "How does inbound email sync work?", **kw}


def test_is_new_question():
    assert is_new_question(_msg(), BOT)
    assert is_new_question(_msg(text="anyone know where billing webhooks live"), BOT)
    assert not is_new_question(_msg(text="thanks!"), BOT)
    assert not is_new_question(_msg(text="FYI deploy is done today"), BOT)
    assert not is_new_question(_msg(user=BOT), BOT)
    assert not is_new_question(_msg(bot_id="B1"), BOT)
    assert not is_new_question(_msg(subtype="channel_join"), BOT)
    assert not is_new_question(_msg(thread_ts="99.0"), BOT)  # reply inside a thread
    assert is_new_question(_msg(thread_ts="100.1"), BOT)  # thread root


def test_slack_links_make_absolute_app_links():
    cites = [Citation(id="1", title="t", url="https://github.com/x/pull/1", source="github"),
             Citation(id="2", title="t", url="/artifacts/seed-thread-0042", source="seed")]
    assert slack_links("Webhooks [1][2]. Odd [7].", cites, "http://app") == \
        "Webhooks <https://github.com/x/pull/1|[1]><http://app/artifacts/seed-thread-0042|[2]>. Odd [7]."


def test_format_reply():
    marcus = Expert(person_id="marcus-lee", name="Marcus Lee", team="Integrations", role="r", topic="messaging",
                    expertise=5, rank_score=3, evidence_summary="Reviewed 38 of Dana's Messaging PRs", evidence=[],
                    badge="recommended",
                    availability=Availability(person_id="marcus-lee", booked_pct=0.35, open_reviews=2, factor=0.585))
    a = Answered(text="Webhooks enqueue a job [1].",
                 citations=[Citation(id="1", title="t", url="https://gh/1", source="github")],
                 experts=[marcus], routing="", contact=marcus, dm="")
    assert format_reply(a, "http://app").splitlines() == [
        "Webhooks enqueue a job <https://gh/1|[1]>.",
        "",
        "*Who knows this*",
        "• *Marcus Lee* (Integrations): reviewed 38 of Dana's Messaging PRs · 35% booked this week · *best bet*",
        "",
        "_Want a DM drafted or time booked? Ask in <http://app|Pinpoint>._",
    ]
