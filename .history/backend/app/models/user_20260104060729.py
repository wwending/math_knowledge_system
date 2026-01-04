from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import relationship
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    
    # --- 新增：角色字段 ---
    role = Column(String, default="user") 

    # 之前加的关系字段要保留
    questions = relationship("app.models.question.Question", back_populates="owner")