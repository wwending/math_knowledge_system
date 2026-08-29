from sqlalchemy import Column, DateTime, ForeignKey, ForeignKeyConstraint, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class QuestionFigure(Base):
    __tablename__ = "question_figures"
    __table_args__ = (
        UniqueConstraint("stable_id", name="uq_question_figures_stable_id"),
        UniqueConstraint("question_id", "id", name="uq_question_figures_question_id_id"),
    )

    id = Column(Integer, primary_key=True)
    stable_id = Column(String(36), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, index=True)
    source_asset_id = Column(Integer, ForeignKey("source_assets.id"), nullable=False)
    figure_asset_id = Column(Integer, ForeignKey("source_assets.id"), nullable=False)
    source_crop_bbox = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    question = relationship("Question", back_populates="figures")
    source_asset = relationship(
        "SourceAsset",
        back_populates="source_question_figures",
        foreign_keys=[source_asset_id],
    )
    figure_asset = relationship(
        "SourceAsset",
        back_populates="materialized_question_figures",
        foreign_keys=[figure_asset_id],
    )
    revision_links = relationship(
        "QuestionRevisionFigure",
        back_populates="figure",
        cascade="all, delete-orphan",
        overlaps="figure_links,revision",
    )


class QuestionRevisionFigure(Base):
    __tablename__ = "question_revision_figures"
    __table_args__ = (
        ForeignKeyConstraint(
            ["question_id", "question_revision_id"],
            ["question_revisions.question_id", "question_revisions.id"],
            name="fk_question_revision_figures_revision_scope",
        ),
        ForeignKeyConstraint(
            ["question_id", "question_figure_id"],
            ["question_figures.question_id", "question_figures.id"],
            name="fk_question_revision_figures_figure_scope",
        ),
        UniqueConstraint(
            "question_revision_id",
            "question_figure_id",
            name="uq_question_revision_figures_revision_figure",
        ),
    )

    id = Column(Integer, primary_key=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    question_revision_id = Column(Integer, nullable=False, index=True)
    question_figure_id = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    revision = relationship(
        "QuestionRevision",
        back_populates="figure_links",
        overlaps="revision_links",
    )
    figure = relationship(
        "QuestionFigure",
        back_populates="revision_links",
        overlaps="figure_links,revision",
    )


class PaperItemFigureSnapshot(Base):
    __tablename__ = "paper_item_figure_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "paper_item_id",
            "figure_stable_id",
            name="uq_paper_item_figure_snapshots_item_figure",
        ),
    )

    id = Column(Integer, primary_key=True)
    paper_item_id = Column(
        Integer,
        ForeignKey("paper_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    figure_stable_id = Column(String(36), nullable=False)
    figure_asset_id = Column(Integer, ForeignKey("source_assets.id"), nullable=False)
    source_asset_id = Column(Integer, ForeignKey("source_assets.id"), nullable=True)
    source_crop_bbox = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    paper_item = relationship("PaperItem", back_populates="figure_snapshots")
    figure_asset = relationship(
        "SourceAsset",
        back_populates="paper_figure_snapshots",
        foreign_keys=[figure_asset_id],
    )
    source_asset = relationship("SourceAsset", foreign_keys=[source_asset_id])
