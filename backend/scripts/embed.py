"""Embed every artifact that has no embedding yet. Resumable: rerun after a crash.

    uv run python -m scripts.embed [--all]
"""

import argparse
import time

import db
from embeddings import embed_documents

BATCH = 256


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="re-embed everything")
    args = parser.parse_args()

    with db.connect() as conn:
        if args.all:
            conn.execute("update artifacts set embedding = null")
        rows = conn.execute("select id, text from artifacts where embedding is null order by id").fetchall()
        print(f"embedding {len(rows)} artifacts")
        start = time.time()
        for i in range(0, len(rows), BATCH):
            batch = rows[i : i + BATCH]
            vectors = embed_documents([text for _, text in batch])
            with conn.cursor() as cur:
                cur.executemany(
                    "update artifacts set embedding = %s where id = %s",
                    [(vec, id_) for (id_, _), vec in zip(batch, vectors)],
                )
            conn.commit()  # commit per batch so a crash keeps progress
            print(f"  {min(i + BATCH, len(rows))}/{len(rows)} ({time.time() - start:.0f}s)")


if __name__ == "__main__":
    main()
