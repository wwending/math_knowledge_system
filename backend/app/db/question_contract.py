from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


LEGACY_QUESTION_COLUMNS: tuple[tuple[str, str], ...] = (
    ("content", "TEXT"),
    ("knowledge_tags", "JSON"),
    ("origin_image", "VARCHAR"),
)


def ensure_legacy_question_columns(engine: Engine) -> Sequence[str]:
    inspector = inspect(engine)
    if "questions" not in inspector.get_table_names():
        return ()

    existing_columns = {column["name"] for column in inspector.get_columns("questions")}
    missing_columns = [item for item in LEGACY_QUESTION_COLUMNS if item[0] not in existing_columns]
    if not missing_columns:
        return ()

    with engine.begin() as connection:
        for column_name, column_type in missing_columns:
            connection.execute(text(f"ALTER TABLE questions ADD COLUMN {column_name} {column_type}"))

    return tuple(column_name for column_name, _ in missing_columns)
