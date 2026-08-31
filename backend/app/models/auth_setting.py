from sqlalchemy import Boolean, Column, DateTime, Integer
from sqlalchemy.sql import func

from app.db.base import Base


class AuthSetting(Base):
    __tablename__ = "auth_settings"

    id = Column(Integer, primary_key=True)
    public_signup_enabled = Column(Boolean, nullable=False)
    updated_by = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
