from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Paper(Base):
    __tablename__ = "papers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="draft")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    items = relationship(
        "PaperItem",
        back_populates="paper",
        cascade="all, delete-orphan",
        order_by="PaperItem.position",
    )


class PaperItem(Base):
    __tablename__ = "paper_items"
    __table_args__ = (
        UniqueConstraint("paper_id", "question_id", name="uq_paper_items_paper_id_question_id"),
        UniqueConstraint("paper_id", "position", name="uq_paper_items_paper_id_position"),
    )

    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(Integer, ForeignKey("papers.id"), nullable=False, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False, index=True)
    question_revision_id = Column(Integer, ForeignKey("question_revisions.id"), nullable=True)
    position = Column(Integer, nullable=False)
    score = Column(Float, nullable=True, default=0)
    content_snapshot = Column(Text, nullable=False)
    answer_snapshot = Column(Text, nullable=True)
    analysis_snapshot = Column(Text, nullable=True)
    knowledge_tags_snapshot = Column(JSON, nullable=True)
    question_type_snapshot = Column(String, nullable=True)
    difficulty_level_snapshot = Column(Integer, nullable=True)
    difficulty_label_snapshot = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    paper = relationship("Paper", back_populates="items")
    question = relationship("Question")
    question_revision = relationship("QuestionRevision")
