import os
import sqlite3
import subprocess
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]


def _alembic(db_path: Path, *args: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    env["UPLOAD_DIR"] = str(db_path.parent / "uploads")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_response_line_migration_backfills_six_checks_bounds_and_round_trips(tmp_path):
    db_path = tmp_path / "response-lines.db"
    _alembic(db_path, "upgrade", "20260830_0011")
    connection = sqlite3.connect(db_path)
    connection.execute(
        "INSERT INTO users (id, username, display_name, hashed_password, role, status, must_change_password) "
        "VALUES (1, 'owner', 'Owner', 'x', 'user', 'active', 0)"
    )
    connection.execute("INSERT INTO questions (id, user_id, content, metadata_generation) VALUES (1, 1, 'stem', 0)")
    connection.execute("INSERT INTO papers (id, user_id, title, status) VALUES (1, 1, 'Paper', 'draft')")
    connection.execute(
        "INSERT INTO paper_items (id, paper_id, question_id, position, score, content_snapshot) "
        "VALUES (1, 1, 1, 1, 0, 'historic')"
    )
    connection.commit()
    connection.close()

    _alembic(db_path, "upgrade", "head")
    connection = sqlite3.connect(db_path)
    assert connection.execute("SELECT response_line_count FROM paper_items WHERE id=1").fetchone()[0] == 6
    for value in (0, 24):
        connection.execute("UPDATE paper_items SET response_line_count=? WHERE id=1", (value,))
        connection.commit()
    for value in (-1, 25):
        try:
            connection.execute("UPDATE paper_items SET response_line_count=? WHERE id=1", (value,))
            connection.commit()
        except sqlite3.IntegrityError:
            connection.rollback()
        else:
            raise AssertionError(f"database accepted response_line_count={value}")
    connection.close()

    _alembic(db_path, "downgrade", "20260830_0011")
    connection = sqlite3.connect(db_path)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(paper_items)")}
    connection.close()
    assert "response_line_count" not in columns
