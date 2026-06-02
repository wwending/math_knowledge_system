from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class LLMRun(Base):
    __tablename__ = "llm_runs"

    id = Column(Integer, primary_key=True, index=True)
    draft_id = Column(Integer, ForeignKey("drafts.id"), nullable=False)
    provider = Column(String, nullable=False, default="deepseek")
    model = Column(String, nullable=True)
    model_version = Column(String, nullable=True)
    prompt_version = Column(String, nullable=False, default="v1")
    input_text = Column(Text, nullable=True)
    raw_output = Column(Text, nullable=True)
    parsed_output = Column(JSON, nullable=True)
    json_valid = Column(Boolean, nullable=False, default=False)
    schema_valid = Column(Boolean, nullable=False, default=False)
    repair_attempted = Column(Boolean, nullable=False, default=False)
    fallback_used = Column(Boolean, nullable=False, default=False)
    latency_ms = Column(Integer, nullable=True)
    error_code = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    draft = relationship("Draft", back_populates="llm_runs", foreign_keys=[draft_id])
    question_revisions = relationship("QuestionRevision", back_populates="llm_run")