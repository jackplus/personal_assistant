from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def _table_columns(engine: Engine, table_name: str) -> set[str]:
    inspector = inspect(engine)
    return {c["name"] for c in inspector.get_columns(table_name)}


def ensure_phase1_schema(engine: Engine) -> None:
    columns = _table_columns(engine, "tasks")
    ddl_statements: list[str] = []

    if "source_platform" not in columns:
        ddl_statements.append("ALTER TABLE tasks ADD COLUMN source_platform VARCHAR(32) DEFAULT 'telegram'")
    if "work_category" not in columns:
        ddl_statements.append("ALTER TABLE tasks ADD COLUMN work_category VARCHAR(64)")

    if not ddl_statements:
        return

    with engine.begin() as conn:
        for ddl in ddl_statements:
            conn.execute(text(ddl))
