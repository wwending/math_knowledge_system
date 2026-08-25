"""feedback inbox (#98)"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260825_0008"
down_revision = "20260825_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feedbacks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category", sa.String(), nullable=False, server_default="bug"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_feedbacks_id", "feedbacks", ["id"], unique=False)
    op.create_index("ix_feedbacks_user_id", "feedbacks", ["user_id"], unique=False)
    op.create_index("ix_feedbacks_status", "feedbacks", ["status"], unique=False)

    op.create_table(
        "feedback_screenshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("feedback_id", sa.Integer(), sa.ForeignKey("feedbacks.id"), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_feedback_screenshots_id", "feedback_screenshots", ["id"], unique=False)
    op.create_index("ix_feedback_screenshots_feedback_id", "feedback_screenshots", ["feedback_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_feedback_screenshots_feedback_id", table_name="feedback_screenshots")
    op.drop_index("ix_feedback_screenshots_id", table_name="feedback_screenshots")
    op.drop_table("feedback_screenshots")

    op.drop_index("ix_feedbacks_status", table_name="feedbacks")
    op.drop_index("ix_feedbacks_user_id", table_name="feedbacks")
    op.drop_index("ix_feedbacks_id", table_name="feedbacks")
    op.drop_table("feedbacks")
