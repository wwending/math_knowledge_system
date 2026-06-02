"""paper mvp"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260527_0003"
down_revision = "20260320_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "papers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_papers_id", "papers", ["id"], unique=False)
    op.create_index("ix_papers_user_id", "papers", ["user_id"], unique=False)

    op.create_table(
        "paper_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("paper_id", sa.Integer(), sa.ForeignKey("papers.id"), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id"), nullable=False),
        sa.Column("question_revision_id", sa.Integer(), sa.ForeignKey("question_revisions.id"), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True, server_default="0"),
        sa.Column("content_snapshot", sa.Text(), nullable=False),
        sa.Column("answer_snapshot", sa.Text(), nullable=True),
        sa.Column("analysis_snapshot", sa.Text(), nullable=True),
        sa.Column("knowledge_tags_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("paper_id", "question_id", name="uq_paper_items_paper_id_question_id"),
        sa.UniqueConstraint("paper_id", "position", name="uq_paper_items_paper_id_position"),
    )
    op.create_index("ix_paper_items_id", "paper_items", ["id"], unique=False)
    op.create_index("ix_paper_items_paper_id", "paper_items", ["paper_id"], unique=False)
    op.create_index("ix_paper_items_question_id", "paper_items", ["question_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_paper_items_question_id", table_name="paper_items")
    op.drop_index("ix_paper_items_paper_id", table_name="paper_items")
    op.drop_index("ix_paper_items_id", table_name="paper_items")
    op.drop_table("paper_items")

    op.drop_index("ix_papers_user_id", table_name="papers")
    op.drop_index("ix_papers_id", table_name="papers")
    op.drop_table("papers")
