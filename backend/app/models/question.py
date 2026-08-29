from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=True)
    answer = Column(Text, nullable=True)
    analysis = Column(Text, nullable=True)
    section_snapshot = Column(JSON, nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    purge_at = Column(DateTime(timezone=True), nullable=True, index=True)
    purged_at = Column(DateTime(timezone=True), nullable=True, index=True)
    metadata_generation = Column(Integer, nullable=False, default=0, server_default="0")
    knowledge_tags = Column(JSON, nullable=True)
    question_type = Column(String, nullable=True)
    difficulty_level = Column(Integer, nullable=True)
    difficulty_label = Column(String, nullable=True)
    difficulty_confidence = Column(Float, nullable=True)
    difficulty_reason = Column(Text, nullable=True)
    difficulty_model = Column(String, nullable=True)
    difficulty_evaluated_at = Column(DateTime(timezone=True), nullable=True)
    metadata_status = Column(String, nullable=True)
    metadata_error = Column(String, nullable=True)
    metadata_started_at = Column(DateTime(timezone=True), nullable=True)
    metadata_finished_at = Column(DateTime(timezone=True), nullable=True)
    origin_image = Column(String, nullable=True)
    # The question's own figure crop (#58); mirrors the origin_image pattern.
    figure_image = Column(String, nullable=True)
    figure_crop_bbox = Column(JSON, nullable=True)
    canonical_fingerprint = Column(String, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    revisions = relationship("QuestionRevision", back_populates="question", cascade="all, delete-orphan")
    figures = relationship("QuestionFigure", back_populates="question")
