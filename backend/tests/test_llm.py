from types import SimpleNamespace

import pytest

import llm


class CountingClient:
    def __init__(self, content):
        self.calls = 0
        message = SimpleNamespace(content=content)

        def create(**_):
            self.calls += 1
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    monkeypatch.setenv("LLM_MODEL", "test-model")


MSGS = [{"role": "user", "content": "hi"}]


def test_cache_replays_without_calling_the_model():
    c = CountingClient('{"answer": "x"}')
    assert llm.cached_chat(MSGS, validate=lambda s: s, client_=c) == '{"answer": "x"}'
    assert llm.cached_chat(MSGS, validate=lambda s: s, client_=c) == '{"answer": "x"}'
    assert c.calls == 1


def test_invalid_replies_are_not_cached():
    def reject(_):
        raise ValueError("bad")

    c = CountingClient("garbage")
    for _ in range(2):
        with pytest.raises(ValueError):
            llm.cached_chat(MSGS, validate=reject, client_=c)
    assert c.calls == 2


def test_different_prompts_are_different_keys():
    c = CountingClient("ok")
    llm.cached_chat(MSGS, validate=lambda s: s, client_=c)
    llm.cached_chat([{"role": "user", "content": "other"}], validate=lambda s: s, client_=c)
    assert c.calls == 2
