from contextlib import contextmanager

import psycopg
from pgvector.psycopg import register_vector

import config


@contextmanager
def connect(vector: bool = True):
    if not config.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env.")
    # prepare_threshold=None: the Supabase pooler doesn't support prepared statements
    with psycopg.connect(config.DATABASE_URL, prepare_threshold=None) as conn:
        if vector:
            register_vector(conn)
        yield conn


def ping() -> bool:
    if not config.DATABASE_URL:
        return False
    try:
        with connect(vector=False) as conn:
            conn.execute("select 1")
        return True
    except psycopg.Error:
        return False
