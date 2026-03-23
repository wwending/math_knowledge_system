"""auth production baseline"""

from __future__ import annotations

from collections.abc import Iterable

from alembic import op
import sqlalchemy as sa


revision = "20260319_0001"
down_revision = None
branch_labels = None
depends_on = None


def _table_names(bind) -> set[str]:
    inspector = sa.inspect(bind)
    return set(inspector.get_table_names())


def _column_names(bind, table_name: str) -> set[str]:
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(bind, table_name: str) -> set[str]:
    inspector = sa.inspect(bind)
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _foreign_keys(bind, table_name: str) -> list[dict]:
    inspector = sa.inspect(bind)
    return inspector.get_foreign_keys(table_name)


def _has_foreign_key(bind, table_name: str, constrained_columns: list[str], referred_table: str) -> bool:
    for foreign_key in _foreign_keys(bind, table_name):
        if (
            foreign_key.get("referred_table") == referred_table
            and foreign_key.get("constrained_columns") == constrained_columns
        ):
            return True
    return False


def _create_indexes(table_name: str, expected: Iterable[tuple[str, list[str], bool]], bind) -> None:
    existing_indexes = _index_names(bind, table_name)
    for index_name, columns, unique in expected:
        if index_name not in existing_indexes:
            op.create_index(index_name, table_name, columns, unique=unique)


def upgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)

    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("username", sa.String(), nullable=True),
            sa.Column("email", sa.String(), nullable=True),
            sa.Column("phone", sa.String(), nullable=True),
            sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("display_name", sa.String(), nullable=False),
            sa.Column("hashed_password", sa.String(), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False, server_default="user"),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
    else:
        user_columns = _column_names(bind, "users")
        if "phone" not in user_columns:
            op.add_column("users", sa.Column("phone", sa.String(), nullable=True))
        if "phone_verified_at" not in user_columns:
            op.add_column("users", sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True))
        if "display_name" not in user_columns:
            op.add_column("users", sa.Column("display_name", sa.String(), nullable=True))
            op.execute(sa.text("UPDATE users SET display_name = COALESCE(display_name, username, 'User')"))
        if "status" not in user_columns:
            op.add_column("users", sa.Column("status", sa.String(length=32), nullable=True))
            if "is_active" in user_columns:
                op.execute(
                    sa.text(
                        "UPDATE users SET status = CASE "
                        "WHEN COALESCE(is_active, 1) = 1 THEN 'active' ELSE 'disabled' END "
                        "WHERE status IS NULL"
                    )
                )
            else:
                op.execute(sa.text("UPDATE users SET status = 'active' WHERE status IS NULL"))
        if "must_change_password" not in user_columns:
            op.add_column(
                "users",
                sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
            )
        else:
            op.execute(sa.text("UPDATE users SET must_change_password = COALESCE(must_change_password, 0)"))
        if "last_login_at" not in user_columns:
            op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
        if "password_changed_at" not in user_columns:
            op.add_column("users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True))
            op.execute(
                sa.text(
                    "UPDATE users SET password_changed_at = COALESCE(password_changed_at, CURRENT_TIMESTAMP)"
                )
            )
        if "created_by" not in user_columns:
            op.add_column("users", sa.Column("created_by", sa.Integer(), nullable=True))
        if "created_at" not in user_columns:
            op.add_column(
                "users",
                sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            )
            op.execute(sa.text("UPDATE users SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)"))
        if "updated_at" not in user_columns:
            op.add_column(
                "users",
                sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            )
            op.execute(sa.text("UPDATE users SET updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)"))
        op.execute(sa.text("UPDATE users SET role = COALESCE(role, 'user')"))
        op.execute(sa.text("UPDATE users SET status = COALESCE(status, 'active')"))
        op.execute(sa.text("UPDATE users SET display_name = COALESCE(display_name, username, phone, 'User')"))
        op.execute(sa.text("UPDATE users SET must_change_password = COALESCE(must_change_password, 0)"))
        op.execute(sa.text("UPDATE users SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP)"))
        op.execute(sa.text("UPDATE users SET updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)"))
        op.execute(
            sa.text(
                "UPDATE users SET phone = username "
                "WHERE phone IS NULL AND username GLOB '[0-9]*' AND LENGTH(username) BETWEEN 6 AND 20"
            )
        )
        with op.batch_alter_table("users", recreate="auto") as batch_op:
            batch_op.alter_column(
                "display_name",
                existing_type=sa.String(),
                nullable=False,
            )
            batch_op.alter_column(
                "status",
                existing_type=sa.String(length=32),
                nullable=False,
                server_default="active",
            )
            batch_op.alter_column(
                "must_change_password",
                existing_type=sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
            batch_op.alter_column(
                "created_at",
                existing_type=sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
            batch_op.alter_column(
                "updated_at",
                existing_type=sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
            if not _has_foreign_key(bind, "users", ["created_by"], "users"):
                batch_op.create_foreign_key(
                    "fk_users_created_by_users",
                    "users",
                    ["created_by"],
                    ["id"],
                )

    _create_indexes(
        "users",
        (
            ("ix_users_id", ["id"], False),
            ("ix_users_username", ["username"], True),
            ("ix_users_email", ["email"], True),
            ("ix_users_phone", ["phone"], True),
        ),
        bind,
    )

    if "questions" not in tables:
        op.create_table(
            "questions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("knowledge_tags", sa.JSON(), nullable=True),
            sa.Column("origin_image", sa.String(), nullable=True),
            sa.Column("canonical_fingerprint", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
    else:
        question_columns = _column_names(bind, "questions")
        if "content" not in question_columns:
            op.add_column("questions", sa.Column("content", sa.Text(), nullable=True))
        if "knowledge_tags" not in question_columns:
            op.add_column("questions", sa.Column("knowledge_tags", sa.JSON(), nullable=True))
        if "origin_image" not in question_columns:
            op.add_column("questions", sa.Column("origin_image", sa.String(), nullable=True))
        if "canonical_fingerprint" not in question_columns:
            op.add_column("questions", sa.Column("canonical_fingerprint", sa.String(), nullable=True))
        if "created_at" not in question_columns:
            op.add_column(
                "questions",
                sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            )
        if "updated_at" not in question_columns:
            op.add_column(
                "questions",
                sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            )

    _create_indexes(
        "questions",
        (
            ("ix_questions_id", ["id"], False),
            ("ix_questions_canonical_fingerprint", ["canonical_fingerprint"], False),
        ),
        bind,
    )

    if "source_assets" not in tables:
        op.create_table(
            "source_assets",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("kind", sa.String(), nullable=False),
            sa.Column("original_path", sa.String(), nullable=False),
            sa.Column("normalized_path", sa.String(), nullable=True),
            sa.Column("mime", sa.String(), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False),
            sa.Column("width", sa.Integer(), nullable=True),
            sa.Column("height", sa.Integer(), nullable=True),
            sa.Column("sha256", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
    _create_indexes(
        "source_assets",
        (
            ("ix_source_assets_id", ["id"], False),
            ("ix_source_assets_sha256", ["sha256"], True),
        ),
        bind,
    )

    if "drafts" not in tables:
        op.create_table(
            "drafts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("source_asset_id", sa.Integer(), sa.ForeignKey("source_assets.id"), nullable=False),
            sa.Column("crop_bbox", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("current_content", sa.JSON(), nullable=True),
            sa.Column("last_ocr_run_id", sa.Integer(), sa.ForeignKey("ocr_runs.id"), nullable=True),
            sa.Column("last_llm_run_id", sa.Integer(), sa.ForeignKey("llm_runs.id"), nullable=True),
            sa.Column("superseded_by_draft_id", sa.Integer(), sa.ForeignKey("drafts.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
    _create_indexes("drafts", (("ix_drafts_id", ["id"], False),), bind)

    if "ocr_runs" not in tables:
        op.create_table(
            "ocr_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("draft_id", sa.Integer(), sa.ForeignKey("drafts.id"), nullable=False),
            sa.Column("provider", sa.String(), nullable=False, server_default="baidu"),
            sa.Column("endpoint", sa.String(), nullable=True),
            sa.Column("request_params_redacted", sa.JSON(), nullable=True),
            sa.Column("response_raw_json", sa.JSON(), nullable=True),
            sa.Column("parsed_blocks", sa.JSON(), nullable=True),
            sa.Column("latency_ms", sa.Integer(), nullable=True),
            sa.Column("error_code", sa.String(), nullable=True),
            sa.Column("error_message", sa.String(), nullable=True),
            sa.Column("text_len_estimate", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
    _create_indexes("ocr_runs", (("ix_ocr_runs_id", ["id"], False),), bind)

    if "llm_runs" not in tables:
        op.create_table(
            "llm_runs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("draft_id", sa.Integer(), sa.ForeignKey("drafts.id"), nullable=False),
            sa.Column("provider", sa.String(), nullable=False, server_default="deepseek"),
            sa.Column("model", sa.String(), nullable=True),
            sa.Column("model_version", sa.String(), nullable=True),
            sa.Column("prompt_version", sa.String(), nullable=False, server_default="v1"),
            sa.Column("input_text", sa.Text(), nullable=True),
            sa.Column("raw_output", sa.Text(), nullable=True),
            sa.Column("parsed_output", sa.JSON(), nullable=True),
            sa.Column("json_valid", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("schema_valid", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("repair_attempted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("latency_ms", sa.Integer(), nullable=True),
            sa.Column("error_code", sa.String(), nullable=True),
            sa.Column("error_message", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
    _create_indexes("llm_runs", (("ix_llm_runs_id", ["id"], False),), bind)

    if "draft_events" not in tables:
        op.create_table(
            "draft_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("draft_id", sa.Integer(), sa.ForeignKey("drafts.id"), nullable=False),
            sa.Column("from_status", sa.String(), nullable=True),
            sa.Column("to_status", sa.String(), nullable=False),
            sa.Column("event_type", sa.String(), nullable=False),
            sa.Column("metadata", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
    _create_indexes("draft_events", (("ix_draft_events_id", ["id"], False),), bind)

    if "question_revisions" not in tables:
        op.create_table(
            "question_revisions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id"), nullable=False),
            sa.Column("rev_no", sa.Integer(), nullable=False),
            sa.Column("content", sa.JSON(), nullable=False),
            sa.Column("crop_bbox", sa.JSON(), nullable=True),
            sa.Column("source_asset_id", sa.Integer(), sa.ForeignKey("source_assets.id"), nullable=True),
            sa.Column("ocr_run_id", sa.Integer(), sa.ForeignKey("ocr_runs.id"), nullable=True),
            sa.Column("llm_run_id", sa.Integer(), sa.ForeignKey("llm_runs.id"), nullable=True),
            sa.Column("change_reason", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint(
                "question_id",
                "rev_no",
                name="uq_question_revisions_question_id_rev_no",
            ),
        )
    _create_indexes("question_revisions", (("ix_question_revisions_id", ["id"], False),), bind)

    if "auth_sessions" not in tables:
        op.create_table(
            "auth_sessions",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("refresh_token_hash", sa.String(length=128), nullable=False),
            sa.Column("auth_method", sa.String(length=32), nullable=False, server_default="password"),
            sa.Column("auth_context", sa.JSON(), nullable=True),
            sa.Column("user_agent", sa.String(), nullable=True),
            sa.Column("created_by_ip", sa.String(length=64), nullable=True),
            sa.Column("last_seen_ip", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_reason", sa.String(length=128), nullable=True),
        )
    _create_indexes(
        "auth_sessions",
        (
            ("ix_auth_sessions_id", ["id"], False),
            ("ix_auth_sessions_user_id", ["user_id"], False),
            ("ix_auth_sessions_refresh_token_hash", ["refresh_token_hash"], True),
        ),
        bind,
    )


def downgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)
    for table_name in (
        "auth_sessions",
        "question_revisions",
        "draft_events",
        "llm_runs",
        "ocr_runs",
        "drafts",
        "source_assets",
        "questions",
        "users",
    ):
        if table_name in tables:
            op.drop_table(table_name)
