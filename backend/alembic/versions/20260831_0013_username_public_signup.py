"""username accounts and persistent public signup governance

Revision ID: 20260831_0013
Revises: 20260830_0012
"""
import os
from alembic import op
import sqlalchemy as sa

revision = "20260831_0013"
down_revision = "20260830_0012"
branch_labels = None
depends_on = None


def _initial_public_signup_enabled() -> bool:
    value = os.getenv("PUBLIC_SIGNUP_ENABLED")
    return True if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


def upgrade() -> None:
    op.create_table(
        "auth_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("public_signup_enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "signup_rate_limits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ip_address", sa.String(64), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("ip_address", name="uq_signup_rate_limits_ip"),
    )
    op.create_index("ix_signup_rate_limits_ip_address", "signup_rate_limits", ["ip_address"])
    op.bulk_insert(sa.table("auth_settings", sa.column("id", sa.Integer()), sa.column("public_signup_enabled", sa.Boolean())), [{"id": 1, "public_signup_enabled": _initial_public_signup_enabled()}])
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("display_name_key", sa.String(), nullable=True))
        batch_op.create_unique_constraint("uq_users_display_name_key", ["display_name_key"])
        batch_op.create_index("ix_users_display_name_key", ["display_name_key"], unique=False)
    op.execute("UPDATE users SET must_change_password = 0, status = 'active' WHERE status = 'pending_password_change'")
    op.execute("UPDATE users SET must_change_password = 0 WHERE must_change_password != 0")
    op.execute(
        """
        CREATE TRIGGER trg_users_preserve_last_super_admin
        BEFORE UPDATE OF role, status ON users
        WHEN OLD.role = 'super_admin'
          AND OLD.status != 'disabled'
          AND (NEW.role != 'super_admin' OR NEW.status = 'disabled')
          AND (SELECT COUNT(*) FROM users WHERE role = 'super_admin' AND status != 'disabled') <= 1
        BEGIN
          SELECT RAISE(ABORT, 'cannot remove last active super_admin');
        END
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_users_preserve_last_super_admin")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_display_name_key")
        batch_op.drop_constraint("uq_users_display_name_key", type_="unique")
        batch_op.drop_column("display_name_key")
    op.drop_table("auth_settings")
    op.drop_index("ix_signup_rate_limits_ip_address", table_name="signup_rate_limits")
    op.drop_table("signup_rate_limits")
