from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.db.base import Base

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    
    # 👇 关键！必须加上这行，关联到 users 表
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    origin_image = Column(String, nullable=True)
    content = Column(Text, nullable=True) # 存放 OCR/DeepSeek 结果
    knowledge_tags = Column(JSON, nullable=True)   # 存放知识点标签
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())