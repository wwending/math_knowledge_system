# backend/app/models/question.py

from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    image_url = Column(String, nullable=False)
    content = Column(Text, nullable=True)
    knowledge_tags = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 新增字段
    owner_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default="pending")

    # --- 关键对应 ---
    # 这里的 back_populates="questions" 必须对应 User 类里的 questions 属性名
    owner = relationship("app.models.user.User", back_populates="questions")