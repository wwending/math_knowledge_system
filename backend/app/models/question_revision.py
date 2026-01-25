from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class QuestionRevision(Base):
    __tablename__ = "question_revisions"
    __table_args__ = (
        UniqueConstraint("question_id", "rev_no", name="uq_question_revisions_question_id_rev_no"),
    )

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    rev_no = Column(Integer, nullable=False)
    content = Column(JSON, nullable=False)
    crop_bbox = Column(JSON, nullable=True)
    source_asset_id = Column(Integer, ForeignKey("source_assets.id"), nullable=True)
    ocr_run_id = Column(Integer, ForeignKey("ocr_runs.id"), nullable=True)
    llm_run_id = Column(Integer, ForeignKey("llm_runs.id"), nullable=True)
    change_reason = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    question = relationship("Question", back_populates="revisions")
    source_asset = relationship("SourceAsset", back_populates="question_revisions")
    ocr_run = relationship("OCRRun", back_populates="question_revisions")
    llm_run = relationship("LLMRun", back_populates="question_revisions")