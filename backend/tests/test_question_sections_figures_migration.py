import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.question import Question
from app.models.question_figure import QuestionFigure, QuestionRevisionFigure
from app.models.question_revision import QuestionRevision
from app.models.source_asset import SourceAsset
from app.models.user import User

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


def test_upgrade_backfills_only_current_and_latest_revision_and_downgrades(tmp_path):
    db_path = tmp_path / "migration.db"
    _alembic(db_path, "upgrade", "20260828_0009")

    connection = sqlite3.connect(db_path)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute(
        "INSERT INTO users (id, username, display_name, hashed_password, role, status, must_change_password) "
        "VALUES (1, 'owner', 'Owner', 'x', 'user', 'active', 0)"
    )
    connection.execute(
        "INSERT INTO source_assets "
        "(id, user_id, kind, original_path, mime, size_bytes, sha256) "
        "VALUES (1, 1, 'image', 'source.png', 'image/png', 10, 'source-sha')"
    )
    connection.execute(
        "INSERT INTO source_assets "
        "(id, user_id, kind, original_path, mime, size_bytes, sha256) "
        "VALUES (2, 1, 'figure', 'figure.png', 'image/png', 5, 'figure-sha')"
    )
    connection.execute(
        "INSERT INTO questions "
        "(id, user_id, content, answer, analysis, figure_image, figure_crop_bbox, metadata_generation) "
        "VALUES (1, 1, 'current stem', 'current answer', NULL, 'figure.png', '[0.1,0.2,0.3,0.4]', 0)"
    )
    connection.execute(
        "INSERT INTO question_revisions "
        "(id, question_id, rev_no, content, source_asset_id, figure_asset_id, change_reason) "
        "VALUES (1, 1, 1, '{\"text\":\"old stem\"}', 1, NULL, 'old')"
    )
    connection.execute(
        "INSERT INTO question_revisions "
        "(id, question_id, rev_no, content, source_asset_id, figure_asset_id, change_reason) "
        "VALUES (2, 1, 2, '{\"text\":\"latest stem\",\"answer\":\"latest answer\"}', 1, 2, 'latest')"
    )
    connection.execute(
        "INSERT INTO papers (id, user_id, title, status) VALUES (1, 1, 'Paper', 'draft')"
    )
    connection.execute(
        "INSERT INTO paper_items "
        "(id, paper_id, question_id, question_revision_id, position, score, content_snapshot) "
        "VALUES (1, 1, 1, 2, 1, 0, 'historic snapshot')"
    )
    connection.commit()
    connection.close()

    _alembic(db_path, "upgrade", "head")

    connection = sqlite3.connect(db_path)
    current = connection.execute(
        "SELECT section_snapshot FROM questions WHERE id=1"
    ).fetchone()[0]
    old_revision = connection.execute(
        "SELECT section_snapshot FROM question_revisions WHERE id=1"
    ).fetchone()[0]
    latest_revision = connection.execute(
        "SELECT section_snapshot FROM question_revisions WHERE id=2"
    ).fetchone()[0]
    paper_snapshot = connection.execute(
        "SELECT section_snapshot FROM paper_items WHERE id=1"
    ).fetchone()[0]
    assert '"schema_version": 2' in current
    assert old_revision is None
    assert '"latest stem"' in latest_revision
    assert paper_snapshot is None
    assert connection.execute("SELECT COUNT(*) FROM question_figures").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM question_revision_figures").fetchone()[0] == 1
    connection.close()

    _alembic(db_path, "downgrade", "20260828_0009")
    connection = sqlite3.connect(db_path)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(questions)")}
    assert "section_snapshot" not in columns
    assert connection.execute("SELECT content FROM questions WHERE id=1").fetchone()[0] == "current stem"
    assert connection.execute("SELECT content_snapshot FROM paper_items WHERE id=1").fetchone()[0] == "historic snapshot"
    connection.close()


def test_composite_foreign_keys_reject_cross_question_revision_figure_links():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        user = User(
            username="owner",
            display_name="Owner",
            hashed_password="x",
            role="user",
            status="active",
        )
        db.add(user)
        db.flush()
        source = SourceAsset(
            user_id=user.id,
            kind="image",
            original_path="source.png",
            mime="image/png",
            size_bytes=1,
            sha256="source",
        )
        figure_asset = SourceAsset(
            user_id=user.id,
            kind="figure",
            original_path="figure.png",
            mime="image/png",
            size_bytes=1,
            sha256="figure",
        )
        first = Question(user_id=user.id, content="first")
        second = Question(user_id=user.id, content="second")
        db.add_all([source, figure_asset, first, second])
        db.flush()
        revision = QuestionRevision(
            question_id=first.id,
            rev_no=1,
            content={"text": "first"},
            change_reason="test",
        )
        figure = QuestionFigure(
            stable_id="d26548c2-e52c-4abc-9cad-19fc0db17ae0",
            question_id=second.id,
            source_asset_id=source.id,
            figure_asset_id=figure_asset.id,
            source_crop_bbox=[0, 0, 1, 1],
        )
        db.add_all([revision, figure])
        db.flush()
        db.add(
            QuestionRevisionFigure(
                question_id=first.id,
                question_revision_id=revision.id,
                question_figure_id=figure.id,
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()
        engine.dispose()
