"""Create all tables and seed the rule catalogue.

    python -m app.init_db            # create tables (if missing) + seed rules
    python -m app.init_db --purge    # also delete prompts past their retention date
    python -m app.init_db --sql      # print the PostgreSQL CREATE TABLE statements instead
"""
import argparse

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.db import models  # noqa: F401  (registers the tables on Base.metadata)
from app.db.base import Base, SessionLocal, engine
from app.db.repository import purge_expired
from app.db.seed import seed_rules


def postgres_ddl() -> str:
    dialect = postgresql.dialect()
    parts = []
    for table in Base.metadata.sorted_tables:
        parts.append(str(CreateTable(table).compile(dialect=dialect)).strip() + ";")
        for index in sorted(table.indexes, key=lambda i: i.name):
            parts.append(str(CreateIndex(index).compile(dialect=dialect)).strip() + ";")
    return "\n\n".join(parts) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--purge", action="store_true", help="delete expired prompts")
    parser.add_argument("--sql", action="store_true", help="print PostgreSQL DDL and exit")
    args = parser.parse_args()

    if args.sql:
        print(postgres_ddl())
        return

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        added = seed_rules(db)
        print(f"Database ready at {engine.url.render_as_string(hide_password=True)} "
              f"({len(Base.metadata.tables)} tables, {added} rules added)")
        if args.purge:
            print(f"Purged {purge_expired(db)} expired prompts")


if __name__ == "__main__":
    main()
