from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Draft(Base):
    __tablename__ = "drafts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    source_asset_id = Column(Integer, ForeignKey("source_assets.id"), nullable=False)
    crop_bbox = Column(JSON, nullable=False)
    status = Column(String, nullable=False)
    current_content = Column(JSON, nullable=True)
    question_type = Column(String, nullable=True)
    difficulty_level = Column(Integer, nullable=True)
    difficulty_label = Column(String, nullable=True)
    difficulty_confidence = Column(Float, nullable=True)
    difficulty_reason = Column(Text, nullable=True)
    last_ocr_run_id = Column(Integer, ForeignKey("ocr_runs.id"), nullable=True)
    last_llm_run_id = Column(Integer, ForeignKey("llm_runs.id"), nullable=True)
    superseded_by_draft_id = Column(Integer, ForeignKey("drafts.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    source_asset = relationship("SourceAsset", back_populates="drafts")
    ocr_runs = relationship(
        "OCRRun",
        back_populates="draft",
        cascade="all, delete-orphan",
        foreign_keys="OCRRun.draft_id",
    )
    llm_runs = relationship(
        "LLMRun",
        back_populates="draft",
        cascade="all, delete-orphan",
        foreign_keys="LLMRun.draft_id",
    )
    last_ocr_run = relationship("OCRRun", foreign_keys=[last_ocr_run_id], post_update=True)
    last_llm_run = relationship("LLMRun", foreign_keys=[last_llm_run_id], post_update=True)
    superseded_by_draft = relationship(
        "Draft",
        remote_side="Draft.id",
        foreign_keys=[superseded_by_draft_id],
    )
    events = relationship("DraftEvent", back_populates="draft", cascade="all, delete-orphan")
