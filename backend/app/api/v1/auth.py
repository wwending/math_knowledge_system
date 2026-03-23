from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Body, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    PasswordValidationError,
    create_access_token,
    generate_refresh_token,
    get_password_hash,
    get_refresh_token_hash,
    normalize_datetime,
    normalize_phone,
    utcnow,
    validate_password_strength,
    verify_password,
)
from app.models.auth_session import AuthSession
from app.models.user import ADMIN_ROLES, User, UserStatus
from app.schemas.auth import (
    AuthCapabilitiesResponse,
    AuthTokenResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
    LoginRequest,
    LogoutResponse,
    RefreshRequest,
    RegisterRequest,
    UserResponse,
)
from app.services.auth_security import (
    AUTH_LOGIN_FAILURE,
    AUTH_LOGIN_SUCCESS,
    AUTH_PASSWORD_CHANGED,
    LoginRateLimitExceededError,
    build_rate_limit_scopes,
    clear_failed_login_state,
    ensure_login_allowed,
    record_failed_login,
    write_auth_audit_log,
)


LOGIN_REQUIRED_MESSAGE = "Login required"
INVALID_TOKEN_MESSAGE = "Invalid login state"
EXPIRED_TOKEN_MESSAGE = "Login expired"
BAD_CREDENTIALS_MESSAGE = "Invalid phone or password"
DISABLED_USER_MESSAGE = "User account is disabled"
ADMIN_REQUIRED_MESSAGE = "Administrator permission required"
PUBLIC_SIGNUP_DISABLED_MESSAGE = "Public signup is disabled in this environment"
REFRESH_TOKEN_REQUIRED_MESSAGE = "Refresh token is required"
WEAK_PASSWORD_MESSAGE = "Password does not meet the security policy"
PASSWORD_CHANGE_REQUIRED_MESSAGE = "Password change is required before accessing this resource"
RATE_LIMITED_LOGIN_MESSAGE = "Too many failed login attempts. Please try again later"


router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False,
)


@dataclass
class AuthContext:
    user: User
    session: AuthSession


def _access_token_ttl() -> timedelta:
    return timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)


def _refresh_token_ttl() -> timedelta:
    return timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)


def _raise_auth_error(detail: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _client_ip(request: Request) -> Optional[str]:
    if request.client and request.client.host:
        return request.client.host
    return None


def _request_user_agent(request: Request) -> Optional[str]:
    return request.headers.get("user-agent")


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    max_age = int(_refresh_token_ttl().total_seconds())
    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME_NORMALIZED,
        value=refresh_token,
        httponly=True,
        secure=settings.REFRESH_TOKEN_COOKIE_SECURE,
        samesite=settings.REFRESH_TOKEN_COOKIE_SAMESITE_NORMALIZED,
        path=settings.REFRESH_TOKEN_COOKIE_PATH_NORMALIZED,
        max_age=max_age,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME_NORMALIZED,
        path=settings.REFRESH_TOKEN_COOKIE_PATH_NORMALIZED,
        secure=settings.REFRESH_TOKEN_COOKIE_SECURE,
        samesite=settings.REFRESH_TOKEN_COOKIE_SAMESITE_NORMALIZED,
    )


def _normalize_phone_or_422(raw_phone: str) -> str:
    try:
        return normalize_phone(raw_phone)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _normalize_phone_for_scope(raw_phone: str) -> Optional[str]:
    candidate = (raw_phone or "").strip()
    if not candidate:
        return None
    try:
        return normalize_phone(candidate)
    except ValueError:
        return candidate[:128]


def _validate_password_or_422(password: str, *, phone: Optional[str], display_name: Optional[str]) -> None:
    try:
        validate_password_strength(password, phone=phone, display_name=display_name)
    except PasswordValidationError as exc:
        raise HTTPException(status_code=422, detail=f"{WEAK_PASSWORD_MESSAGE}: {exc}") from exc


def _build_access_token(user: User, session: AuthSession) -> str:
    return create_access_token(
        data={
            "sub": str(user.id),
            "sid": session.id,
            "typ": "access",
            "role": user.role,
        },
        expires_delta=_access_token_ttl(),
    )


def _build_auth_response(user: User, session: AuthSession) -> AuthTokenResponse:
    return AuthTokenResponse(
        access_token=_build_access_token(user, session),
        expires_in=int(_access_token_ttl().total_seconds()),
        user=UserResponse.model_validate(user),
    )


def _requires_password_change(user: User) -> bool:
    return (
        user.must_change_password
        or user.status == UserStatus.PENDING_PASSWORD_CHANGE.value
    )


def _get_user_by_phone(db: Session, phone: str) -> Optional[User]:
    return (
        db.query(User)
        .filter(
            or_(
                User.phone == phone,
                and_(User.phone.is_(None), User.username == phone),
            )
        )
        .first()
    )


def _get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def _get_session_by_refresh_token(db: Session, refresh_token: str) -> Optional[AuthSession]:
    token_hash = get_refresh_token_hash(refresh_token)
    return db.query(AuthSession).filter(AuthSession.refresh_token_hash == token_hash).first()


def _is_session_active(session: Optional[AuthSession]) -> bool:
    if session is None or session.revoked_at is not None:
        return False
    expires_at = normalize_datetime(session.expires_at)
    return bool(expires_at and expires_at > utcnow())


def _revoke_session(session: AuthSession, *, reason: str) -> None:
    if session.revoked_at is None:
        session.revoked_at = utcnow()
        session.revoked_reason = reason


def _revoke_user_sessions(
    db: Session,
    *,
    user_id: int,
    reason: str,
    exclude_session_id: Optional[str] = None,
) -> None:
    sessions = db.query(AuthSession).filter(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None)).all()
    for session in sessions:
        if exclude_session_id and session.id == exclude_session_id:
            continue
        _revoke_session(session, reason=reason)


def _create_session(
    db: Session,
    *,
    user: User,
    request: Request,
    auth_method: str = "password",
) -> tuple[AuthSession, str]:
    refresh_token = generate_refresh_token()
    now = utcnow()
    session = AuthSession(
        id=str(uuid4()),
        user_id=user.id,
        refresh_token_hash=get_refresh_token_hash(refresh_token),
        auth_method=auth_method,
        auth_context={"phone_verification": None},
        user_agent=_request_user_agent(request),
        created_by_ip=_client_ip(request),
        last_seen_ip=_client_ip(request),
        last_used_at=now,
        expires_at=now + _refresh_token_ttl(),
    )
    db.add(session)
    return session, refresh_token


def _rotate_refresh_session(db: Session, session: AuthSession, request: Request) -> str:
    refresh_token = generate_refresh_token()
    session.refresh_token_hash = get_refresh_token_hash(refresh_token)
    session.last_used_at = utcnow()
    session.last_seen_ip = _client_ip(request)
    session.user_agent = _request_user_agent(request)
    session.expires_at = utcnow() + _refresh_token_ttl()
    db.add(session)
    return refresh_token


def _decode_access_token(token: str) -> tuple[int, str]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("typ") != "access":
            _raise_auth_error(INVALID_TOKEN_MESSAGE)
        user_id = int(payload.get("sub"))
        session_id = payload.get("sid")
        if not session_id:
            _raise_auth_error(INVALID_TOKEN_MESSAGE)
        return user_id, session_id
    except ExpiredSignatureError:
        _raise_auth_error(EXPIRED_TOKEN_MESSAGE)
    except (JWTError, TypeError, ValueError):
        _raise_auth_error(INVALID_TOKEN_MESSAGE)


def get_auth_context(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme),
) -> AuthContext:
    if not token:
        _raise_auth_error(LOGIN_REQUIRED_MESSAGE)

    user_id, session_id = _decode_access_token(token)
    user = _get_user_by_id(db, user_id)
    if not user:
        _raise_auth_error(INVALID_TOKEN_MESSAGE)

    session = db.query(AuthSession).filter(AuthSession.id == session_id, AuthSession.user_id == user_id).first()
    if not _is_session_active(session):
        _raise_auth_error(INVALID_TOKEN_MESSAGE)

    if user.status == UserStatus.DISABLED.value:
        _revoke_session(session, reason="user_disabled")
        db.commit()
        raise HTTPException(status_code=403, detail=DISABLED_USER_MESSAGE)

    return AuthContext(user=user, session=session)


def get_current_user(context: AuthContext = Depends(get_auth_context)) -> User:
    return context.user


def get_current_session(context: AuthContext = Depends(get_auth_context)) -> AuthSession:
    return context.session


def require_active_user(context: AuthContext = Depends(get_auth_context)) -> User:
    if _requires_password_change(context.user):
        raise HTTPException(status_code=403, detail=PASSWORD_CHANGE_REQUIRED_MESSAGE)
    return context.user


def require_admin(user: User = Depends(require_active_user)) -> User:
    if user.role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail=ADMIN_REQUIRED_MESSAGE)
    return user


@router.get("/capabilities", response_model=AuthCapabilitiesResponse)
def read_auth_capabilities():
    return AuthCapabilitiesResponse(
        public_signup_enabled=settings.PUBLIC_SIGNUP_ENABLED,
        password_recovery_mode=settings.PASSWORD_RECOVERY_MODE,
        sms_code_login_enabled=settings.SMS_CODE_LOGIN_ENABLED,
        sms_password_recovery_enabled=settings.SMS_PASSWORD_RECOVERY_ENABLED,
    )


@router.post("/register", response_model=UserResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    if not settings.PUBLIC_SIGNUP_ENABLED:
        raise HTTPException(status_code=403, detail=PUBLIC_SIGNUP_DISABLED_MESSAGE)

    normalized_phone = _normalize_phone_or_422(payload.phone)
    _validate_password_or_422(payload.password, phone=normalized_phone, display_name=payload.display_name)

    if _get_user_by_phone(db, normalized_phone):
        raise HTTPException(status_code=409, detail="Phone number already exists")

    now = utcnow()
    user = User(
        username=normalized_phone,
        phone=normalized_phone,
        display_name=payload.display_name.strip(),
        hashed_password=get_password_hash(payload.password),
        role="user",
        status=UserStatus.ACTIVE.value,
        must_change_password=False,
        password_changed_at=now,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _login_user(db: Session, response: Response, request: Request, *, phone: str, password: str) -> AuthTokenResponse:
    client_ip = _client_ip(request)
    user_agent = _request_user_agent(request)
    login_scopes = build_rate_limit_scopes(phone=_normalize_phone_for_scope(phone), ip_address=client_ip)

    try:
        ensure_login_allowed(db, scopes=login_scopes)
    except LoginRateLimitExceededError as exc:
        write_auth_audit_log(
            db,
            event_type=AUTH_LOGIN_FAILURE,
            outcome="rate_limited",
            target_phone=_normalize_phone_for_scope(phone),
            ip_address=client_ip,
            user_agent=user_agent,
            details={"reason": "too_many_failed_attempts", "retry_after_seconds": exc.retry_after_seconds},
        )
        db.commit()
        raise HTTPException(
            status_code=429,
            detail=RATE_LIMITED_LOGIN_MESSAGE,
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from exc

    try:
        normalized_phone = _normalize_phone_or_422(phone)
    except HTTPException as exc:
        record_failed_login(db, scopes=login_scopes)
        write_auth_audit_log(
            db,
            event_type=AUTH_LOGIN_FAILURE,
            outcome="failure",
            target_phone=_normalize_phone_for_scope(phone),
            ip_address=client_ip,
            user_agent=user_agent,
            details={"reason": "invalid_phone_format"},
        )
        db.commit()
        raise exc

    user = _get_user_by_phone(db, normalized_phone)
    if not user or not verify_password(password, user.hashed_password):
        record_failed_login(db, scopes=login_scopes)
        write_auth_audit_log(
            db,
            event_type=AUTH_LOGIN_FAILURE,
            outcome="failure",
            target_phone=normalized_phone,
            ip_address=client_ip,
            user_agent=user_agent,
            details={"reason": "bad_credentials"},
        )
        db.commit()
        _raise_auth_error(BAD_CREDENTIALS_MESSAGE)
    if user.status == UserStatus.DISABLED.value:
        record_failed_login(db, scopes=login_scopes)
        write_auth_audit_log(
            db,
            event_type=AUTH_LOGIN_FAILURE,
            outcome="failure",
            actor_user=user,
            target_user=user,
            ip_address=client_ip,
            user_agent=user_agent,
            details={"reason": "user_disabled"},
        )
        db.commit()
        raise HTTPException(status_code=403, detail=DISABLED_USER_MESSAGE)

    clear_failed_login_state(db, scopes=login_scopes)
    session, refresh_token = _create_session(db, user=user, request=request)
    user.last_login_at = utcnow()
    db.add(user)
    write_auth_audit_log(
        db,
        event_type=AUTH_LOGIN_SUCCESS,
        outcome="success",
        actor_user=user,
        target_user=user,
        ip_address=client_ip,
        user_agent=user_agent,
        details={"session_id": session.id, "auth_method": session.auth_method},
    )
    db.commit()
    db.refresh(user)
    db.refresh(session)

    _set_refresh_cookie(response, refresh_token)
    return _build_auth_response(user, session)


@router.post("/login", response_model=AuthTokenResponse)
def login(payload: LoginRequest, response: Response, request: Request, db: Session = Depends(get_db)):
    return _login_user(db, response, request, phone=payload.phone, password=payload.password)


@router.post("/token", response_model=AuthTokenResponse)
def login_for_legacy_token(
    response: Response,
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    return _login_user(db, response, request, phone=form_data.username, password=form_data.password)


@router.post("/refresh", response_model=AuthTokenResponse)
def refresh_access_token(
    response: Response,
    request: Request,
    payload: Optional[RefreshRequest] = Body(default=None),
    refresh_cookie: Optional[str] = Cookie(default=None, alias=settings.REFRESH_TOKEN_COOKIE_NAME_NORMALIZED),
    db: Session = Depends(get_db),
):
    payload = payload or RefreshRequest()
    refresh_token = refresh_cookie or payload.refresh_token
    if not refresh_token:
        _raise_auth_error(REFRESH_TOKEN_REQUIRED_MESSAGE)

    session = _get_session_by_refresh_token(db, refresh_token)
    if not _is_session_active(session):
        _raise_auth_error(INVALID_TOKEN_MESSAGE)

    user = _get_user_by_id(db, session.user_id)
    if not user:
        _revoke_session(session, reason="user_missing")
        db.commit()
        _raise_auth_error(INVALID_TOKEN_MESSAGE)
    if user.status == UserStatus.DISABLED.value:
        _revoke_session(session, reason="user_disabled")
        db.commit()
        raise HTTPException(status_code=403, detail=DISABLED_USER_MESSAGE)

    rotated_refresh_token = _rotate_refresh_session(db, session, request)
    db.commit()
    db.refresh(user)
    db.refresh(session)

    _set_refresh_cookie(response, rotated_refresh_token)
    return _build_auth_response(user, session)


@router.post("/logout", response_model=LogoutResponse)
def logout(
    response: Response,
    payload: Optional[RefreshRequest] = Body(default=None),
    refresh_cookie: Optional[str] = Cookie(default=None, alias=settings.REFRESH_TOKEN_COOKIE_NAME_NORMALIZED),
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):
    payload = payload or RefreshRequest()
    session = None
    if token:
        try:
            user_id, session_id = _decode_access_token(token)
            session = db.query(AuthSession).filter(AuthSession.id == session_id, AuthSession.user_id == user_id).first()
        except HTTPException:
            session = None

    if session is None:
        refresh_token = refresh_cookie or payload.refresh_token
        if refresh_token:
            session = _get_session_by_refresh_token(db, refresh_token)

    if session:
        _revoke_session(session, reason="logout")
        db.commit()

    _clear_refresh_cookie(response)
    return LogoutResponse()


@router.get("/me", response_model=UserResponse)
def read_me(user: User = Depends(get_current_user)):
    return user


@router.post("/change-password", response_model=ChangePasswordResponse)
def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    request: Request,
    context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    user = context.user
    client_ip = _client_ip(request)
    user_agent = _request_user_agent(request)
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    _validate_password_or_422(payload.new_password, phone=user.phone, display_name=user.display_name)
    user.hashed_password = get_password_hash(payload.new_password)
    user.password_changed_at = utcnow()
    user.must_change_password = False
    if user.status == UserStatus.PENDING_PASSWORD_CHANGE.value:
        user.status = UserStatus.ACTIVE.value

    _revoke_user_sessions(db, user_id=user.id, reason="password_changed")
    session, refresh_token = _create_session(db, user=user, request=request)
    db.add(user)
    write_auth_audit_log(
        db,
        event_type=AUTH_PASSWORD_CHANGED,
        outcome="success",
        actor_user=user,
        target_user=user,
        ip_address=client_ip,
        user_agent=user_agent,
        details={"session_id": session.id, "auth_method": session.auth_method},
    )
    db.commit()
    db.refresh(user)
    db.refresh(session)

    _set_refresh_cookie(response, refresh_token)
    result = _build_auth_response(user, session)
    return ChangePasswordResponse(
        access_token=result.access_token,
        expires_in=result.expires_in,
        user=result.user,
    )
