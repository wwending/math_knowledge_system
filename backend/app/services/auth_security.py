from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import normalize_datetime, utcnow
from app.models.auth_audit_log import AuthAuditLog
from app.models.login_rate_limit import LoginRateLimit
from app.models.user import User


AUTH_LOGIN_SUCCESS = "auth.login.success"
AUTH_LOGIN_FAILURE = "auth.login.failure"
AUTH_PASSWORD_CHANGED = "auth.password.changed"
ADMIN_USER_CREATED = "admin.user.created"
ADMIN_USER_DISABLED = "admin.user.disabled"
ADMIN_USER_ENABLED = "admin.user.enabled"
ADMIN_USER_ROLE_CHANGED = "admin.user.role.changed"
ADMIN_USER_PASSWORD_RESET = "admin.user.password.reset"
AUTH_SIGNUP_SUCCESS = "auth.signup.success"
AUTH_SIGNUP_RATE_LIMITED = "auth.signup.rate_limited"
ADMIN_PUBLIC_SIGNUP_ENABLED = "admin.public_signup.enabled"
ADMIN_PUBLIC_SIGNUP_DISABLED = "admin.public_signup.disabled"


@dataclass(frozen=True)
class RateLimitScope:
    scope_type: str
    scope_value: str


class LoginRateLimitExceededError(RuntimeError):
    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = max(retry_after_seconds, 1)
        super().__init__("Too many failed login attempts")


def build_rate_limit_scopes(*, phone: Optional[str], ip_address: Optional[str]) -> list[RateLimitScope]:
    scopes: list[RateLimitScope] = []
    if phone:
        scopes.append(RateLimitScope(scope_type="phone", scope_value=phone))
    if ip_address:
        scopes.append(RateLimitScope(scope_type="ip", scope_value=ip_address))
    return scopes


def ensure_login_allowed(db: Session, *, scopes: list[RateLimitScope]) -> None:
    if not scopes:
        return

    now = utcnow()
    filters = [
        (LoginRateLimit.scope_type == scope.scope_type) & (LoginRateLimit.scope_value == scope.scope_value)
        for scope in scopes
    ]
    records = (
        db.query(LoginRateLimit)
        .filter(or_(*filters), LoginRateLimit.blocked_until.is_not(None))
        .all()
    )
    retry_after_seconds = 0
    for record in records:
        blocked_until = normalize_datetime(record.blocked_until)
        if blocked_until and blocked_until > now:
            retry_after_seconds = max(
                retry_after_seconds,
                int((blocked_until - now).total_seconds()),
            )
    if retry_after_seconds > 0:
        raise LoginRateLimitExceededError(retry_after_seconds)


def record_failed_login(db: Session, *, scopes: list[RateLimitScope]) -> None:
    if not scopes:
        return

    now = utcnow()
    window = timedelta(seconds=settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS)
    block = timedelta(seconds=settings.LOGIN_RATE_LIMIT_BLOCK_SECONDS)
    for scope in scopes:
        record = (
            db.query(LoginRateLimit)
            .filter(
                LoginRateLimit.scope_type == scope.scope_type,
                LoginRateLimit.scope_value == scope.scope_value,
            )
            .first()
        )
        if record is None:
            record = LoginRateLimit(
                scope_type=scope.scope_type,
                scope_value=scope.scope_value,
                failed_count=0,
                window_started_at=now,
            )

        window_started_at = normalize_datetime(record.window_started_at)
        blocked_until = normalize_datetime(record.blocked_until)
        if window_started_at is None or now - window_started_at >= window:
            record.failed_count = 0
            record.window_started_at = now
            record.blocked_until = None
        elif blocked_until and blocked_until <= now:
            record.blocked_until = None

        record.failed_count += 1
        record.last_attempt_at = now
        if record.failed_count >= settings.LOGIN_RATE_LIMIT_MAX_ATTEMPTS:
            record.blocked_until = now + block
        db.add(record)


def clear_failed_login_state(db: Session, *, scopes: list[RateLimitScope]) -> None:
    if not scopes:
        return

    for scope in scopes:
        (
            db.query(LoginRateLimit)
            .filter(
                LoginRateLimit.scope_type == scope.scope_type,
                LoginRateLimit.scope_value == scope.scope_value,
            )
            .delete(synchronize_session=False)
        )


def write_auth_audit_log(
    db: Session,
    *,
    event_type: str,
    outcome: str = "success",
    actor_user: Optional[User] = None,
    target_user: Optional[User] = None,
    target_phone: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[dict] = None,
) -> None:
    db.add(
        AuthAuditLog(
            event_type=event_type,
            outcome=outcome,
            actor_user_id=actor_user.id if actor_user else None,
            target_user_id=target_user.id if target_user else None,
            target_phone=target_phone or getattr(target_user, "phone", None),
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or None,
        )
    )
