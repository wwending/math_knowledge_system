from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship # <--- 新增
from app.core.database import Base

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    image_url = Column(String, nullable=False)
    content = Column(Text, nullable=True)
    knowledge_tags = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # --- 新增字段 ---
    # 关联到 User 表
    owner_id = Column(Integer, ForeignKey("users.id"))
    # 审核状态: "pending"(待审核), "approved"(通过), "rejected"(驳回)
    status = Column(String, default="pending")

    # 反向关系 (可选，方便查询)
    owner = relationship("app.models.user.User")