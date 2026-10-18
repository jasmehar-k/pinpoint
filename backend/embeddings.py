"""Local embeddings. Free, no API key, works offline after the first model download."""

from functools import cache

import numpy as np
from fastembed import TextEmbedding

MODEL = "BAAI/bge-small-en-v1.5"
DIMS = 384  # must match artifacts.embedding in schema.sql


@cache
def _model() -> TextEmbedding:
    return TextEmbedding(MODEL)


def embed_documents(texts: list[str], batch_size: int = 64) -> list[np.ndarray]:
    return list(_model().embed(texts, batch_size=batch_size))


def embed_query(text: str) -> np.ndarray:
    # bge uses a query prefix; query_embed applies it.
    return next(iter(_model().query_embed(text)))
