"""question section snapshots and multi-figure foundations (#127)"""

from __future__ import annotations

from typing import Any, Optional
from uuid import NAMESPACE_URL, uuid5

from alembic import op
import sqlalchemy as sa

revision = "20260829_0010"
down_revision = "20260828_0009"
branch_labels = None
depends_on = None


def _stable_uuid(seed: str, *parts: object) -> str:
    value = ":".join(["math-knowledge-system", seed, *(str(part) for part in parts)])
    return str(uuid5(NAMESPACE_URL, value))


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    value = value if isinstance(value, str) else str(value)
    value = value.strip()
    return value or None


def _snapshot(
    *,
    seed: str,
    content: Any,
    answer: Any,
    analysis: Any,
    figure_stable_id: Optional[str] = None,
    height_ratio: float = 1.0,
) -> dict[str, Any]:
    stem = _text(content)
    answer_text = _text(answer)
    analysis_text = _text(analysis)
    stem_blocks = []
    if stem:
        stem_blocks.append(
            {"id": _stable_uuid(seed, "stem", "text", 0), "kind": "text", "markdown": stem}
        )
    if figure_stable_id:
        stem_blocks.append(
            {
                "id": _stable_uuid(seed, "stem", "image_area", 0),
                "kind": "image_area",
                "height_ratio": height_ratio if height_ratio > 0 else 1.0,
                "placements": [
                    {
                        "figure_id": figure_stable_id,
                        "x": 0.0,
                        "y": 0.0,
                        "width": 1.0,
                        "height": 1.0,
                    }
                ],
            }
        )
    value = {
        "schema_version": 2,
        "sections": {
            "stem": {"blocks": stem_blocks},
            "answer": {
                "blocks": [
                    {
                        "id": _stable_uuid(seed, "answer", "text", 0),
                        "kind": "text",
                        "markdown": answer_text,
                    }
                ]
                if answer_text
                else []
            },
            "analysis": {
                "blocks": [
                    {
                        "id": _stable_uuid(seed, "analysis", "text", 0),
                        "kind": "text",
                        "markdown": analysis_text,
                    }
                ]
                if analysis_text
                else []
            },
        },
    }
    if not stem_blocks:
        value["compatibility_state"] = "incomplete_stem"
    return value


def upgrade():
    op.add_column("questions", sa.Column("section_snapshot", sa.JSON(), nullable=True))
    op.add_column("question_revisions", sa.Column("section_snapshot", sa.JSON(), nullable=True))
    op.add_column("paper_items", sa.Column("section_snapshot", sa.JSON(), nullable=True))

    with op.batch_alter_table("question_revisions") as batch_op:
        batch_op.create_unique_constraint(
            "uq_question_revisions_question_id_id",
            ["question_id", "id"],
        )

    op.create_table(
        "question_figures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stable_id", sa.String(length=36), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("source_asset_id", sa.Integer(), nullable=False),
        sa.Column("figure_asset_id", sa.Integer(), nullable=False),
        sa.Column("source_crop_bbox", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
        sa.ForeignKeyConstraint(["source_asset_id"], ["source_assets.id"]),
        sa.ForeignKeyConstraint(["figure_asset_id"], ["source_assets.id"]),
        sa.UniqueConstraint("stable_id", name="uq_question_figures_stable_id"),
        sa.UniqueConstraint("question_id", "id", name="uq_question_figures_question_id_id"),
    )
    op.create_index("ix_question_figures_question_id", "question_figures", ["question_id"])

    op.create_table(
        "question_revision_figures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("question_revision_id", sa.Integer(), nullable=False),
        sa.Column("question_figure_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
        sa.ForeignKeyConstraint(
            ["question_id", "question_revision_id"],
            ["question_revisions.question_id", "question_revisions.id"],
            name="fk_question_revision_figures_revision_scope",
        ),
        sa.ForeignKeyConstraint(
            ["question_id", "question_figure_id"],
            ["question_figures.question_id", "question_figures.id"],
            name="fk_question_revision_figures_figure_scope",
        ),
        sa.UniqueConstraint(
            "question_revision_id",
            "question_figure_id",
            name="uq_question_revision_figures_revision_figure",
        ),
    )
    op.create_index(
        "ix_question_revision_figures_revision_id",
        "question_revision_figures",
        ["question_revision_id"],
    )
    op.create_index(
        "ix_question_revision_figures_figure_id",
        "question_revision_figures",
        ["question_figure_id"],
    )

    op.create_table(
        "paper_item_figure_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("paper_item_id", sa.Integer(), nullable=False),
        sa.Column("figure_stable_id", sa.String(length=36), nullable=False),
        sa.Column("figure_asset_id", sa.Integer(), nullable=False),
        sa.Column("source_asset_id", sa.Integer(), nullable=True),
        sa.Column("source_crop_bbox", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["paper_item_id"], ["paper_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["figure_asset_id"], ["source_assets.id"]),
        sa.ForeignKeyConstraint(["source_asset_id"], ["source_assets.id"]),
        sa.UniqueConstraint(
            "paper_item_id",
            "figure_stable_id",
            name="uq_paper_item_figure_snapshots_item_figure",
        ),
    )
    op.create_index(
        "ix_paper_item_figure_snapshots_item_id",
        "paper_item_figure_snapshots",
        ["paper_item_id"],
    )

    bind = op.get_bind()
    questions = sa.table(
        "questions",
        sa.column("id", sa.Integer()),
        sa.column("content", sa.Text()),
        sa.column("answer", sa.Text()),
        sa.column("analysis", sa.Text()),
        sa.column("figure_crop_bbox", sa.JSON()),
        sa.column("section_snapshot", sa.JSON()),
    )
    revisions = sa.table(
        "question_revisions",
        sa.column("id", sa.Integer()),
        sa.column("question_id", sa.Integer()),
        sa.column("rev_no", sa.Integer()),
        sa.column("content", sa.JSON()),
        sa.column("source_asset_id", sa.Integer()),
        sa.column("figure_asset_id", sa.Integer()),
        sa.column("section_snapshot", sa.JSON()),
    )
    figures = sa.table(
        "question_figures",
        sa.column("id", sa.Integer()),
        sa.column("stable_id", sa.String()),
        sa.column("question_id", sa.Integer()),
        sa.column("source_asset_id", sa.Integer()),
        sa.column("figure_asset_id", sa.Integer()),
        sa.column("source_crop_bbox", sa.JSON()),
    )
    revision_figures = sa.table(
        "question_revision_figures",
        sa.column("question_id", sa.Integer()),
        sa.column("question_revision_id", sa.Integer()),
        sa.column("question_figure_id", sa.Integer()),
    )

    revision_rows = bind.execute(
        sa.select(revisions).order_by(
            revisions.c.question_id,
            revisions.c.rev_no.desc(),
            revisions.c.id.desc(),
        )
    ).mappings().all()
    latest_by_question = {}
    for row in revision_rows:
        latest_by_question.setdefault(row["question_id"], row)

    for question in bind.execute(sa.select(questions)).mappings():
        latest = latest_by_question.get(question["id"])
        legacy = latest["content"] if latest and isinstance(latest["content"], dict) else {}
        content = legacy.get("text") or legacy.get("content") or question["content"]
        answer = legacy.get("answer", question["answer"])
        analysis = legacy.get("analysis", question["analysis"])

        figure_stable_id = None
        figure_row_id = None
        if latest and latest["figure_asset_id"] and latest["source_asset_id"]:
            figure_stable_id = _stable_uuid("question", question["id"], "legacy_figure")
            bind.execute(
                figures.insert().values(
                    stable_id=figure_stable_id,
                    question_id=question["id"],
                    source_asset_id=latest["source_asset_id"],
                    figure_asset_id=latest["figure_asset_id"],
                    source_crop_bbox=question["figure_crop_bbox"] or [0.0, 0.0, 1.0, 1.0],
                )
            )
            figure_row_id = bind.execute(
                sa.select(figures.c.id).where(figures.c.stable_id == figure_stable_id)
            ).scalar_one()

        snapshot = _snapshot(
            seed=f"question:{question['id']}",
            content=content,
            answer=answer,
            analysis=analysis,
            figure_stable_id=figure_stable_id,
        )
        bind.execute(
            questions.update()
            .where(questions.c.id == question["id"])
            .values(section_snapshot=snapshot)
        )
        if latest:
            bind.execute(
                revisions.update()
                .where(revisions.c.id == latest["id"])
                .values(section_snapshot=snapshot)
            )
            if figure_row_id is not None:
                bind.execute(
                    revision_figures.insert().values(
                        question_id=question["id"],
                        question_revision_id=latest["id"],
                        question_figure_id=figure_row_id,
                    )
                )


def downgrade():
    op.drop_index(
        "ix_paper_item_figure_snapshots_item_id",
        table_name="paper_item_figure_snapshots",
    )
    op.drop_table("paper_item_figure_snapshots")
    op.drop_index(
        "ix_question_revision_figures_figure_id",
        table_name="question_revision_figures",
    )
    op.drop_index(
        "ix_question_revision_figures_revision_id",
        table_name="question_revision_figures",
    )
    op.drop_table("question_revision_figures")
    op.drop_index("ix_question_figures_question_id", table_name="question_figures")
    op.drop_table("question_figures")

    with op.batch_alter_table("question_revisions") as batch_op:
        batch_op.drop_constraint(
            "uq_question_revisions_question_id_id",
            type_="unique",
        )

    op.drop_column("paper_items", "section_snapshot")
    op.drop_column("question_revisions", "section_snapshot")
    op.drop_column("questions", "section_snapshot")
