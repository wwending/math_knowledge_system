from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class SourceAsset(Base):
    __tablename__ = "source_assets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    kind = Column(String, nullable=False)
    original_path = Column(String, nullable=False)
    normalized_path = Column(String, nullable=True)
    mime = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    sha256 = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    drafts = relationship("Draft", back_populates="source_asset")
    question_revisions = relationship(
        "QuestionRevision",
        back_populates="source_asset",
        foreign_keys="QuestionRevision.source_asset_id",
    )