"""question metadata status"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260604_0005"
down_revision = "20260604_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("questions", sa.Column("metadata_status", sa.String(), nullable=True))
    op.add_column("questions", sa.Column("metadata_error", sa.String(), nullable=True))
    op.add_column("questions", sa.Column("metadata_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("questions", sa.Column("metadata_finished_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("questions", "metadata_finished_at")
    op.drop_column("questions", "metadata_started_at")
    op.drop_column("questions", "metadata_error")
    op.drop_column("questions", "metadata_status")
