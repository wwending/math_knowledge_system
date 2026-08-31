from __future__ import annotations

import hashlib
import re
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings


SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
RESERVED_ACCOUNT_NAMES = {"admin", "administrator", "root", "system", "superadmin", "super_admin", "管理员", "超级管理员", "系统"}
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
    del phone, display_name
    candidate = password or ""
    if len(candidate) < 6 or len(candidate) > 64:
        raise PasswordValidationError("Password must be 6 to 64 characters")
    if not candidate.strip(" "):
        raise PasswordValidationError("Password cannot contain only spaces")
    if any(ord(char) < 0x20 or ord(char) > 0x7E for char in candidate):
        raise PasswordValidationError("Password must contain printable ASCII characters only")


def normalize_account_name(value: str) -> str:
    return unicodedata.normalize("NFC", (value or "").strip())


def validate_account_name(value: str, *, field_name: str = "Username") -> str:
    normalized = normalize_account_name(value)
    def allowed(char: str) -> bool:
        return char == "_" or (char.isascii() and char.isalnum()) or unicodedata.name(char, "").startswith("CJK UNIFIED IDEOGRAPH")

    if not 1 <= len(normalized) <= 32 or not all(allowed(char) for char in normalized) or not any(char != "_" for char in normalized):
        raise ValueError(f"{field_name} must be 1 to 32 Chinese, letter, digit, or underscore characters")
    if normalized.casefold() in {name.casefold() for name in RESERVED_ACCOUNT_NAMES}:
        raise ValueError(f"{field_name} is reserved")
    return normalized


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
