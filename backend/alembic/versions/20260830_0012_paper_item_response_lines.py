"""add per-paper-item response line count

Revision ID: 20260830_0012
Revises: 20260830_0011
"""

from alembic import op
import sqlalchemy as sa


revision = "20260830_0012"
down_revision = "20260830_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("paper_items") as batch_op:
        batch_op.add_column(sa.Column("response_line_count", sa.Integer(), server_default="6", nullable=False))
        batch_op.create_check_constraint(
            "ck_paper_items_response_line_count",
            "response_line_count >= 0 AND response_line_count <= 24",
        )


def downgrade() -> None:
    with op.batch_alter_table("paper_items") as batch_op:
        batch_op.drop_constraint("ck_paper_items_response_line_count", type_="check")
        batch_op.drop_column("response_line_count")
