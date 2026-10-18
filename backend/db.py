import atexit
from contextlib import contextmanager
from functools import cache

import psycopg
from pgvector.psycopg import register_vector
from psycopg_pool import ConnectionPool

import config


def _configure(conn) -> None:
    register_vector(conn)


@cache
def _pool() -> ConnectionPool:
    if not config.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env.")
    # Opening a connection to Supabase costs ~0.6s; reusing pooled ones makes every request faster.
    # prepare_threshold=None: the Supabase pooler doesn't support prepared statements.
    pool = ConnectionPool(config.DATABASE_URL, min_size=1, max_size=5, open=True,
                          kwargs={"prepare_threshold": None}, configure=_configure)
    atexit.register(pool.close)  # otherwise scripts hang ~5s per pool thread on exit
    return pool


@contextmanager
def connect(vector: bool = True):
    """A pooled connection (pgvector types registered). Commits on success, rolls back on error.
    `vector` is kept for older callers; every pooled connection has vector support."""
    with _pool().connection() as conn:
        yield conn


def ping() -> bool:
    if not config.DATABASE_URL:
        return False
    try:
        with connect() as conn:
            conn.execute("select 1")
        return True
    except (psycopg.Error, RuntimeError):
        return False
