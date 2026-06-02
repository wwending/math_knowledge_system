from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from app.db.base import Base


class LoginRateLimit(Base):
    __tablename__ = "login_rate_limits"
    __table_args__ = (
        UniqueConstraint("scope_type", "scope_value", name="uq_login_rate_limits_scope"),
    )

    id = Column(Integer, primary_key=True, index=True)
    scope_type = Column(String(16), nullable=False)
    scope_value = Column(String(128), nullable=False)
    failed_count = Column(Integer, nullable=False, default=0)
    window_started_at = Column(DateTime(timezone=True), nullable=False)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    blocked_until = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
