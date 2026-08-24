"""question figure assets (#58)"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260825_0006"
down_revision = "20260604_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("drafts", sa.Column("detected_figures", sa.JSON(), nullable=True))
    op.add_column("questions", sa.Column("figure_image", sa.String(), nullable=True))
    op.add_column("questions", sa.Column("figure_crop_bbox", sa.JSON(), nullable=True))
    # SQLite cannot ALTER-add a constraint: batch mode recreates the table
    # so the foreign key lands in the rebuilt schema.
    with op.batch_alter_table("question_revisions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "figure_asset_id",
                sa.Integer(),
                sa.ForeignKey(
                    "source_assets.id", name="fk_question_revisions_figure_asset_id"
                ),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("question_revisions") as batch_op:
        batch_op.drop_column("figure_asset_id")
    op.drop_column("questions", "figure_crop_bbox")
    op.drop_column("questions", "figure_image")
    op.drop_column("drafts", "detected_figures")
