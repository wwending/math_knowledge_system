# backend/app/models/user.py

from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship  # <--- 必须导入这个！
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)

    # --- 关键修改：必须加上这一行 ---
    # 这行代码告诉数据库：User 和 Question 是有关联的
    # 这里的 "owner" 必须对应 Question 类里的 owner 字段的 back_populates 参数
    questions = relationship("app.models.question.Question", back_populates="owner")