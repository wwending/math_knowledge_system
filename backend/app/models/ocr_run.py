from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class OCRRun(Base):
    __tablename__ = "ocr_runs"

    id = Column(Integer, primary_key=True, index=True)
    draft_id = Column(Integer, ForeignKey("drafts.id"), nullable=False)
    provider = Column(String, nullable=False, default="baidu")
    endpoint = Column(String, nullable=True)
    request_params_redacted = Column(JSON, nullable=True)
    response_raw_json = Column(JSON, nullable=True)
    parsed_blocks = Column(JSON, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    error_code = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    text_len_estimate = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    draft = relationship("Draft", back_populates="ocr_runs", foreign_keys=[draft_id])
    question_revisions = relationship("QuestionRevision", back_populates="ocr_run")