from sqlalchemy import Column, Integer, String, Text, JSON, DateTime
from sqlalchemy.sql import func
from app.core.database import Base

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    # 图片存储路径 (相对路径)
    image_url = Column(String, nullable=False)
    # 识别出的原始 Markdown/LaTeX
    content = Column(Text, nullable=True)
    # AI 分析出的知识点 (存 JSON 列表)
    knowledge_tags = Column(JSON, nullable=True)
    # 创建时间
    created_at = Column(DateTime(timezone=True), server_default=func.now())