from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


from app.db.migrations import upgrade_database  # noqa: E402


class FreshMigratedSQLiteDatabase:
    """Isolated SQLite database created from an empty file via Alembic."""

    def __init__(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._temp_dir.name) / "test_migrated.db"
        self.db_url = f"sqlite:///{self.db_path.as_posix()}"

        upgrade_database(self.db_url)

        self.engine = create_engine(
            self.db_url,
            connect_args={"check_same_thread": False},
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def dispose(self) -> None:
        self.engine.dispose()
        self._temp_dir.cleanup()
