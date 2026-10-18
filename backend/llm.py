"""LLM client. OpenRouter speaks the OpenAI API, so any model there is a config change."""

import os
from functools import cache

from openai import OpenAI

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


@cache
def client() -> OpenAI:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set. Copy .env.example to .env.")
    return OpenAI(base_url=OPENROUTER_BASE_URL, api_key=key)


def model() -> str:
    name = os.getenv("LLM_MODEL")
    if not name:
        raise RuntimeError("LLM_MODEL is not set. Pick a free OpenRouter model that supports tool calling.")
    return name
