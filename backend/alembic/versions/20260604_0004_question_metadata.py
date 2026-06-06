"""question metadata"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260604_0004"
down_revision = "20260527_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("questions", sa.Column("question_type", sa.String(), nullable=True))
    op.add_column("questions", sa.Column("difficulty_level", sa.Integer(), nullable=True))
    op.add_column("questions", sa.Column("difficulty_label", sa.String(), nullable=True))
    op.add_column("questions", sa.Column("difficulty_confidence", sa.Float(), nullable=True))
    op.add_column("questions", sa.Column("difficulty_reason", sa.Text(), nullable=True))
    op.add_column("questions", sa.Column("difficulty_model", sa.String(), nullable=True))
    op.add_column("questions", sa.Column("difficulty_evaluated_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("drafts", sa.Column("question_type", sa.String(), nullable=True))
    op.add_column("drafts", sa.Column("difficulty_level", sa.Integer(), nullable=True))
    op.add_column("drafts", sa.Column("difficulty_label", sa.String(), nullable=True))
    op.add_column("drafts", sa.Column("difficulty_confidence", sa.Float(), nullable=True))
    op.add_column("drafts", sa.Column("difficulty_reason", sa.Text(), nullable=True))

    op.add_column("paper_items", sa.Column("question_type_snapshot", sa.String(), nullable=True))
    op.add_column("paper_items", sa.Column("difficulty_level_snapshot", sa.Integer(), nullable=True))
    op.add_column("paper_items", sa.Column("difficulty_label_snapshot", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("paper_items", "difficulty_label_snapshot")
    op.drop_column("paper_items", "difficulty_level_snapshot")
    op.drop_column("paper_items", "question_type_snapshot")

    op.drop_column("drafts", "difficulty_reason")
    op.drop_column("drafts", "difficulty_confidence")
    op.drop_column("drafts", "difficulty_label")
    op.drop_column("drafts", "difficulty_level")
    op.drop_column("drafts", "question_type")

    op.drop_column("questions", "difficulty_evaluated_at")
    op.drop_column("questions", "difficulty_model")
    op.drop_column("questions", "difficulty_reason")
    op.drop_column("questions", "difficulty_confidence")
    op.drop_column("questions", "difficulty_label")
    op.drop_column("questions", "difficulty_level")
    op.drop_column("questions", "question_type")
