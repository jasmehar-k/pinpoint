from types import SimpleNamespace

from connectors.slack import clean_text, normalize_thread, paginate, permalink
from schema import Artifact, Person
from tagging import parse_tags, tag_topics


def _person(id_, name):
    return Person(id=id_, name=name, team="Integrations", role="r", manager=None,
                  github_login=None, slack_handle=id_)


PEOPLE = {"UPRIYA": _person("priya-shah", "Priya Shah"), "UMARCUS": _person("marcus-lee", "Marcus Lee"),
          "UDANA": _person("dana-okafor", "Dana Okafor")}
CHANNEL = {"id": "C0HELP", "name": "help"}
WORKSPACE = "https://acme.slack.com/"


def _msg(user, ts, text="hi", **extra):
    return {"type": "message", "user": user, "ts": ts, "thread_ts": "1760000000.000100", "text": text, **extra}


def _thread():
    return [
        _msg("UPRIYA", "1760000000.000100", "How does inbound email sync work?", reply_count=3),
        _msg("UMARCUS", "1760000100.000200", "Webhooks trigger the message channel sync."),
        _msg("UPRIYA", "1760000200.000300", "Thanks! Where's the job?"),
        _msg("UMARCUS", "1760000300.000400", "MessagingMessageListFetchJob."),
        _msg("UDANA", "1760000400.000500", "Also see the cron fallback."),
    ]


def _normalize(messages):
    return normalize_thread(CHANNEL, messages, PEOPLE, WORKSPACE)


def test_asked_and_answered_events():
    artifact, events = _normalize(_thread())
    assert artifact.id == "slack:C0HELP:1760000000.000100"
    assert artifact.source == "slack" and artifact.kind == "thread"
    assert artifact.title == "#help: How does inbound email sync work?"
    assert artifact.text.splitlines()[:2] == [
        "Priya Shah: How does inbound email sync work?",
        "Marcus Lee: Webhooks trigger the message channel sync.",
    ]
    assert sorted((e.type, e.person_id) for e in events) == [
        ("answered", "dana-okafor"), ("answered", "marcus-lee"), ("asked", "priya-shah"),
    ]
    assert all(e.source == "slack" and e.paths == [] and e.text == artifact.text for e in events)


def test_answer_uses_first_reply_time():
    _, events = _normalize(_thread())
    marcus = next(e for e in events if e.person_id == "marcus-lee")
    assert marcus.timestamp.timestamp() == 1760000100.0002


def test_asker_self_reply_is_not_an_answer():
    _, events = _normalize(_thread()[:3])
    assert [e.type for e in events if e.person_id == "priya-shah"] == ["asked"]


def test_subtype_and_bot_messages_ignored():
    thread = _thread()[:2] + [
        _msg("UDANA", "1760000150.0", "joined", subtype="channel_join"),
        _msg("UDANA", "1760000160.0", "bot says hi", bot_id="B1"),
    ]
    artifact, events = _normalize(thread)
    assert "joined" not in artifact.text and "bot says" not in artifact.text
    assert "dana-okafor" not in {e.person_id for e in events}


def test_replies_api_duplicate_root_is_ignored():
    thread = _thread()[:2] + [_thread()[0]]
    artifact, _ = _normalize(thread)
    assert len(artifact.text.splitlines()) == 2


def test_unknown_users_keep_artifact_without_events():
    thread = [_msg("USTRANGER", "1760000000.000100", "Who owns billing?"),
              _msg("UOTHER", "1760000100.0", "Isabel does.")]
    artifact, events = _normalize(thread)
    assert artifact.text == "Someone: Who owns billing?\nSomeone: Isabel does."
    assert events == []


def test_lone_message_is_an_artifact_with_one_asked_event():
    msg = {"type": "message", "user": "UPRIYA", "ts": "1760000000.000100", "text": "Anyone around?"}
    artifact, events = _normalize([msg])
    assert artifact.url == "https://acme.slack.com/archives/C0HELP/p1760000000000100"
    assert [(e.type, e.person_id) for e in events] == [("asked", "priya-shah")]


def test_thread_with_no_text_after_filtering_is_skipped():
    assert _normalize([_msg("UPRIYA", "1.0", "x", subtype="channel_join")]) == (None, [])
    assert _normalize([_msg("UPRIYA", "1.0", "   ")]) == (None, [])
    assert _normalize([]) == (None, [])


def test_permalink_format():
    assert permalink("https://acme.slack.com/", "C123", "1712345678.123456") == \
        "https://acme.slack.com/archives/C123/p1712345678123456"
    assert permalink("https://acme.slack.com", "C123", "1.5") == "https://acme.slack.com/archives/C123/p15"


def test_long_title_is_truncated():
    artifact, _ = _normalize([_msg("UPRIYA", "1760000000.000100", "word " * 40)])
    assert artifact.title.startswith("#help: word") and artifact.title.endswith("...")
    assert len(artifact.title) <= len("#help: ") + 80 + 3


def test_clean_text():
    text = "<@UMARCUS> see <#C1|deploys> and <https://x.dev|the doc> &amp; <https://y.dev> <!here> <@UX>"
    assert clean_text(text, PEOPLE) == "@Marcus Lee see #deploys and the doc & https://y.dev @here @someone"


def test_paginate_follows_cursor():
    pages = {None: {"items": [1, 2], "response_metadata": {"next_cursor": "c2"}},
             "c2": {"items": [3], "response_metadata": {"next_cursor": ""}}}
    calls = []

    def call(**kwargs):
        calls.append(kwargs)
        return pages[kwargs.get("cursor")]

    assert paginate(call, "items", channel="C1") == [1, 2, 3]
    assert calls[1] == {"channel": "C1", "limit": 200, "cursor": "c2"}


# ---- topic tagging ----

def test_parse_tags_strips_code_fences_and_drops_unknown_ids():
    raw = '```json\n{"t1": ["messaging", "made-up"], "t2": [], "t3": "Auth"}\n```'
    assert parse_tags(raw, ["t1", "t2", "t3", "t4"]) == {
        "t1": ["messaging"], "t2": [], "t3": ["auth"], "t4": [],
    }


def test_parse_tags_accepts_labels_and_caps_at_three():
    raw = 'Sure! {"t1": ["Messaging (email sync)", "auth", "billing", "deploys", "auth"]}'
    assert parse_tags(raw, ["t1"]) == {"t1": ["messaging", "auth", "billing"]}


class FakeLLM:
    """Stands in for the OpenAI client: returns canned replies in order."""

    def __init__(self, replies):
        self.replies, self.calls = list(replies), []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=reply))])


def _artifacts(n):
    return [Artifact(id=f"slack:C1:{i}", source="slack", kind="thread", text=f"thread {i}",
                     url="https://x", timestamp="2026-10-01T00:00:00Z") for i in range(n)]


def test_tag_topics_batches_and_maps_back_to_artifact_ids():
    fake = FakeLLM(['{"t1": ["billing"], "t2": ["auth"]}', '{"t1": ["deploys"]}'])
    tags = tag_topics(_artifacts(3), client=fake, model="m", batch_size=2, pause=0)
    assert tags == {"slack:C1:0": ["billing"], "slack:C1:1": ["auth"], "slack:C1:2": ["deploys"]}
    assert len(fake.calls) == 2


def test_tag_topics_retries_once_on_malformed_json():
    fake = FakeLLM(["not json at all", '{"t1": ["workflow"]}'])
    assert tag_topics(_artifacts(1), client=fake, model="m", pause=0) == {"slack:C1:0": ["workflow"]}
    assert len(fake.calls) == 2


def test_tag_topics_falls_back_to_no_topics_after_two_failures():
    fake = FakeLLM(['{"t1": [', RuntimeError("429 rate limited")])
    assert tag_topics(_artifacts(2), client=fake, model="m", pause=0) == {
        "slack:C1:0": [], "slack:C1:1": [],
    }
    assert len(fake.calls) == 2
