from sqlalchemy import Boolean, Column, Integer, String
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    # role: "user" (普通用户) or "admin" (管理员)
    role = Column(String, default="user") 
    is_active = Column(Boolean, default=True)