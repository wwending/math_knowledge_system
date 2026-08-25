from enum import Enum

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class FeedbackCategory(str, Enum):
    BUG = "bug"
    FEATURE = "feature"
    SUGGESTION = "suggestion"


class FeedbackStatus(str, Enum):
    PENDING = "pending"
    ADOPTED = "adopted"
    REJECTED = "rejected"


class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    category = Column(String, nullable=False, default=FeedbackCategory.BUG.value)
    content = Column(Text, nullable=False)
    status = Column(String, nullable=False, default=FeedbackStatus.PENDING.value, index=True)
    review_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User")
    screenshots = relationship(
        "FeedbackScreenshot",
        back_populates="feedback",
        cascade="all, delete-orphan",
        order_by="FeedbackScreenshot.id",
    )


class FeedbackScreenshot(Base):
    __tablename__ = "feedback_screenshots"

    id = Column(Integer, primary_key=True, index=True)
    feedback_id = Column(Integer, ForeignKey("feedbacks.id"), nullable=False, index=True)
    # Bare filename inside UPLOAD_DIR (same convention as Question.origin_image /
    # PaperItem.figure_image_snapshot); resolved only through
    # app.core.files.resolve_upload_file_path.
    path = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    feedback = relationship("Feedback", back_populates="screenshots")
