from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config


BACKEND_DIR = Path(__file__).resolve().parents[2]


def get_alembic_config(database_url: str | None = None) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    if database_url:
        config.set_main_option("sqlalchemy.url", database_url)
    return config


def upgrade_database(database_url: str | None = None, revision: str = "head") -> None:
    command.upgrade(get_alembic_config(database_url), revision)
