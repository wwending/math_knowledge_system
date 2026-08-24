"""paper item figure snapshots (#59)"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260825_0007"
down_revision = "20260825_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "paper_items",
        sa.Column("figure_image_snapshot", sa.String(), nullable=True),
    )


def downgrade() -> None:
    # SQLite cannot ALTER-drop a column outside batch mode: batch mode
    # recreates the table so the drop lands in the rebuilt schema.
    with op.batch_alter_table("paper_items") as batch_op:
        batch_op.drop_column("figure_image_snapshot")
