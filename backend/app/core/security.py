from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings


SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
COMMON_WEAK_PASSWORDS = {
    "12345678",
    "123456789",
    "1234567890",
    "password",
    "password123",
    "qwerty123",
    "admin123",
    "admin1234",
    "11111111",
    "00000000",
}
PHONE_SANITIZE_PATTERN = re.compile(r"[\s\-\(\)]")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class PasswordValidationError(ValueError):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_datetime(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def normalize_phone(phone: str) -> str:
    normalized = PHONE_SANITIZE_PATTERN.sub("", phone.strip())
    if normalized.startswith("00"):
        normalized = f"+{normalized[2:]}"

    if normalized.startswith("+"):
        digits = normalized[1:]
        if not digits.isdigit():
            raise ValueError("Invalid phone number format")
        normalized_value = normalized
    else:
        if not normalized.isdigit():
            raise ValueError("Invalid phone number format")
        normalized_value = normalized

    digit_count = len(normalized_value.lstrip("+"))
    if digit_count < 6 or digit_count > 20:
        raise ValueError("Invalid phone number format")
    return normalized_value


def validate_password_strength(
    password: str,
    *,
    phone: Optional[str] = None,
    display_name: Optional[str] = None,
) -> None:
    candidate = password or ""
    if len(candidate) < 8:
        raise PasswordValidationError("Password must be at least 8 characters")
    if candidate.isdigit():
        raise PasswordValidationError("Password cannot be numeric only")
    if candidate.lower() in COMMON_WEAK_PASSWORDS:
        raise PasswordValidationError("Password is too weak")

    classes = 0
    classes += 1 if re.search(r"[A-Z]", candidate) else 0
    classes += 1 if re.search(r"[a-z]", candidate) else 0
    classes += 1 if re.search(r"\d", candidate) else 0
    classes += 1 if re.search(r"[^A-Za-z0-9]", candidate) else 0
    if classes < 2:
        raise PasswordValidationError("Password must include at least two character classes")

    lowered = candidate.lower()
    if phone:
        normalized_phone = normalize_phone(phone).lstrip("+")
        if normalized_phone and normalized_phone in lowered:
            raise PasswordValidationError("Password cannot contain the phone number")
    if display_name:
        compact_display_name = re.sub(r"\s+", "", display_name).lower()
        if compact_display_name and len(compact_display_name) >= 3 and compact_display_name in lowered:
            raise PasswordValidationError("Password cannot contain the display name")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def get_refresh_token_hash(refresh_token: str) -> str:
    return hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()
