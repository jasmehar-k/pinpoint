"""LLM client. OpenRouter speaks the OpenAI API, so any model there is a config change."""

import hashlib
import json
import os
from collections.abc import Callable
from functools import cache

from openai import OpenAI

import config  # noqa: F401  loads .env

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def timeout() -> float:
    """Seconds before a chat LLM call gives up and the code-written fallback answer takes over.
    The SDK default is ~10 minutes with retries; one answer once took 135s."""
    return float(os.getenv("LLM_TIMEOUT", "30"))


def client() -> OpenAI:
    """For chat: fails fast. No SDK retries, since a retry doubles the wait and the fallback
    answer beats making someone wait."""
    return _client(timeout(), 0)


def batch_client() -> OpenAI:
    """For offline jobs (seeding, tagging): seed batches take ~2 minutes, so wait and retry."""
    return _client(300.0, 2)


@cache
def _client(seconds: float, retries: int) -> OpenAI:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set. Copy .env.example to .env.")
    return OpenAI(base_url=OPENROUTER_BASE_URL, api_key=key, timeout=seconds, max_retries=retries)


def model() -> str:
    name = os.getenv("LLM_MODEL")
    if not name:
        raise RuntimeError("LLM_MODEL is not set. Pick a free OpenRouter model that supports tool calling.")
    return name


def reasoning() -> dict:
    """Reasoning effort for chat answers. "low" measured ~8s vs ~12s default on Nemotron with the
    same answer quality; "off" was ~3s but refused to answer from the sources."""
    effort = os.getenv("LLM_REASONING", "low")
    return {"reasoning": {"enabled": False}} if effort == "off" else {"reasoning": {"effort": effort}}


# ---- answer cache ----
# Same prompt -> same reply, read from disk. After one rehearsal the demo questions answer instantly
# and keep working if OpenRouter is slow or down. A changed prompt (new sources) is a new key.

CACHE_DIR = config.BACKEND_ROOT / "data" / "llm_cache"


def _key(messages: list[dict], temperature: float) -> str:
    raw = json.dumps({"model": model(), "messages": messages, "temperature": temperature}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def cached_chat(messages: list[dict], validate: Callable[[str], object], temperature: float = 0.3,
                client_=None) -> str:
    """Reply for these messages, from disk if seen before. `validate` must not raise for a reply
    to be cached, so a malformed reply is never replayed."""
    path = CACHE_DIR / f"{_key(messages, temperature)}.json"
    if path.exists():
        return json.loads(path.read_text())["content"]
    res = (client_ or client()).chat.completions.create(
        model=model(), temperature=temperature, messages=messages, extra_body=reasoning())
    content = res.choices[0].message.content or ""
    validate(content)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"messages": messages, "content": content}))
    return content
