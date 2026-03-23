"""auth audit logs and login rate limits"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260320_0002"
down_revision = "20260319_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False, server_default="success"),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("target_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("target_phone", sa.String(length=32), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_auth_audit_logs_id", "auth_audit_logs", ["id"], unique=False)
    op.create_index("ix_auth_audit_logs_event_type", "auth_audit_logs", ["event_type"], unique=False)
    op.create_index("ix_auth_audit_logs_outcome", "auth_audit_logs", ["outcome"], unique=False)
    op.create_index("ix_auth_audit_logs_actor_user_id", "auth_audit_logs", ["actor_user_id"], unique=False)
    op.create_index("ix_auth_audit_logs_target_user_id", "auth_audit_logs", ["target_user_id"], unique=False)
    op.create_index("ix_auth_audit_logs_target_phone", "auth_audit_logs", ["target_phone"], unique=False)
    op.create_index("ix_auth_audit_logs_created_at", "auth_audit_logs", ["created_at"], unique=False)

    op.create_table(
        "login_rate_limits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scope_type", sa.String(length=16), nullable=False),
        sa.Column("scope_value", sa.String(length=128), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("scope_type", "scope_value", name="uq_login_rate_limits_scope"),
    )
    op.create_index("ix_login_rate_limits_id", "login_rate_limits", ["id"], unique=False)
    op.create_index("ix_login_rate_limits_blocked_until", "login_rate_limits", ["blocked_until"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_login_rate_limits_blocked_until", table_name="login_rate_limits")
    op.drop_index("ix_login_rate_limits_id", table_name="login_rate_limits")
    op.drop_table("login_rate_limits")

    op.drop_index("ix_auth_audit_logs_created_at", table_name="auth_audit_logs")
    op.drop_index("ix_auth_audit_logs_target_phone", table_name="auth_audit_logs")
    op.drop_index("ix_auth_audit_logs_target_user_id", table_name="auth_audit_logs")
    op.drop_index("ix_auth_audit_logs_actor_user_id", table_name="auth_audit_logs")
    op.drop_index("ix_auth_audit_logs_outcome", table_name="auth_audit_logs")
    op.drop_index("ix_auth_audit_logs_event_type", table_name="auth_audit_logs")
    op.drop_index("ix_auth_audit_logs_id", table_name="auth_audit_logs")
    op.drop_table("auth_audit_logs")
