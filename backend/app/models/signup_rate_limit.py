from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.db.base import Base


class SignupRateLimit(Base):
    __tablename__ = "signup_rate_limits"

    id = Column(Integer, primary_key=True)
    ip_address = Column(String(64), nullable=False, unique=True, index=True)
    success_count = Column(Integer, nullable=False, default=0)
    success_window_started_at = Column(DateTime(timezone=True), nullable=False)
    failure_count = Column(Integer, nullable=False, default=0)
    failure_window_started_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
