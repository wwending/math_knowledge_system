"""persist paper answer and analysis display options

Revision ID: 20260830_0011
Revises: 20260829_0010
"""

from alembic import op
import sqlalchemy as sa


revision = "20260830_0011"
down_revision = "20260829_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("papers") as batch_op:
        batch_op.add_column(sa.Column("show_answer", sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column("show_analysis", sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    with op.batch_alter_table("papers") as batch_op:
        batch_op.drop_column("show_analysis")
        batch_op.drop_column("show_answer")
