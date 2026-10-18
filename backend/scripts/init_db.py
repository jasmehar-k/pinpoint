"""Create tables. Safe to rerun."""

import config
import db


def main() -> None:
    sql = (config.BACKEND_ROOT / "schema.sql").read_text()
    with db.connect(vector=False) as conn:
        conn.execute(sql)
    print("schema applied")


if __name__ == "__main__":
    main()
