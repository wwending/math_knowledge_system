from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    USER = "user"


class UserStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    PENDING_PASSWORD_CHANGE = "pending_password_change"


ADMIN_ROLES = {UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value}


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=True)
    email = Column(String, unique=True, index=True, nullable=True)
    phone = Column(String, unique=True, index=True, nullable=True)
    phone_verified_at = Column(DateTime(timezone=True), nullable=True)
    display_name = Column(String, nullable=False)
    display_name_key = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False, default=UserRole.USER.value)
    status = Column(String, nullable=False, default=UserStatus.ACTIVE.value)
    must_change_password = Column(Boolean, nullable=False, default=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    password_changed_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    creator = relationship("User", remote_side=[id], foreign_keys=[created_by])
    auth_sessions = relationship("AuthSession", back_populates="user")

    @property
    def is_active(self) -> bool:
        return self.status != UserStatus.DISABLED.value
