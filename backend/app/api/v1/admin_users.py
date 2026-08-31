from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.auth import require_super_admin
from app.core.database import get_db
from app.core.security import (
    PasswordValidationError,
    get_password_hash,
    normalize_phone,
    validate_account_name,
    utcnow,
    validate_password_strength,
)
from app.models.auth_session import AuthSession
from app.models.auth_setting import AuthSetting
from app.models.user import User, UserRole, UserStatus
from app.schemas.auth import (
    AdminCreateUserRequest,
    AdminMutationResponse,
    AdminResetPasswordRequest,
    AdminUserListResponse,
    PublicSignupSettingResponse,
    UpdateUserRoleRequest,
    UpdateUserStatusRequest,
    UpdatePublicSignupSettingRequest,
    UserResponse,
)
from app.services.auth_security import (
    ADMIN_USER_CREATED,
    ADMIN_USER_DISABLED,
    ADMIN_USER_ENABLED,
    ADMIN_USER_PASSWORD_RESET,
    ADMIN_USER_ROLE_CHANGED,
    ADMIN_PUBLIC_SIGNUP_DISABLED,
    ADMIN_PUBLIC_SIGNUP_ENABLED,
    write_auth_audit_log,
)


router = APIRouter(prefix="/admin/users", tags=["admin-users"])
SELF_STATUS_CHANGE_FORBIDDEN_MESSAGE = "Administrators cannot change their own status"
SELF_ROLE_CHANGE_FORBIDDEN_MESSAGE = "Administrators cannot change their own role"
SELF_PASSWORD_RESET_FORBIDDEN_MESSAGE = "Administrators cannot reset their own password from the admin endpoint"
STATUS_MUTATION_FORBIDDEN_MESSAGE = "Status endpoint only supports active or disabled"


def _normalize_phone_or_422(raw_phone: str) -> str:
    try:
        return normalize_phone(raw_phone)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _validate_password_or_422(password: str, *, phone: Optional[str], display_name: Optional[str]) -> None:
    try:
        validate_password_strength(password, phone=phone, display_name=display_name)
    except PasswordValidationError as exc:
        raise HTTPException(status_code=422, detail=f"Password does not meet the security policy: {exc}") from exc


def _get_user_or_404(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _is_super_admin(user: User) -> bool:
    return user.role == UserRole.SUPER_ADMIN.value


def _active_super_admin_count(db: Session) -> int:
    return (
        db.query(User)
        .filter(
            User.role == UserRole.SUPER_ADMIN.value,
            User.status != UserStatus.DISABLED.value,
        )
        .count()
    )


def _ensure_manageable(current_admin: User, target_user: User) -> None:
    if _is_super_admin(target_user) and not _is_super_admin(current_admin):
        raise HTTPException(status_code=403, detail="Only super_admin can manage a super_admin")


def _ensure_role_assignable(current_admin: User, role: str) -> None:
    if role == UserRole.SUPER_ADMIN.value and not _is_super_admin(current_admin):
        raise HTTPException(status_code=403, detail="Only super_admin can assign the super_admin role")


def _ensure_not_last_super_admin(db: Session, target_user: User, *, next_role: Optional[str] = None, next_status: Optional[str] = None) -> None:
    if not _is_super_admin(target_user):
        return

    role_after_change = next_role or target_user.role
    status_after_change = next_status or target_user.status
    if role_after_change == UserRole.SUPER_ADMIN.value and status_after_change != UserStatus.DISABLED.value:
        return

    if _active_super_admin_count(db) <= 1:
        raise HTTPException(status_code=409, detail="Cannot downgrade or disable the only super_admin")


def _revoke_user_sessions(db: Session, *, user_id: int, reason: str) -> None:
    sessions = db.query(AuthSession).filter(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None)).all()
    now = utcnow()
    for session in sessions:
        session.revoked_at = now
        session.revoked_reason = reason


def _ensure_not_self_status_change(current_admin: User, target_user: User) -> None:
    if current_admin.id == target_user.id:
        raise HTTPException(status_code=409, detail=SELF_STATUS_CHANGE_FORBIDDEN_MESSAGE)


def _ensure_not_self_role_change(current_admin: User, target_user: User) -> None:
    if current_admin.id == target_user.id:
        raise HTTPException(status_code=409, detail=SELF_ROLE_CHANGE_FORBIDDEN_MESSAGE)


def _ensure_not_self_password_reset(current_admin: User, target_user: User) -> None:
    if current_admin.id == target_user.id:
        raise HTTPException(status_code=409, detail=SELF_PASSWORD_RESET_FORBIDDEN_MESSAGE)


def _request_user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def _request_ip(request: Request) -> str | None:
    if request.client and request.client.host:
        return request.client.host
    return None


@router.post("", response_model=UserResponse)
def create_user(
    payload: AdminCreateUserRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_super_admin),
):
    if payload.role == UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=422, detail="Create user only supports user or admin")
    try:
        username = validate_account_name(payload.username)
        display_name = validate_account_name(payload.display_name or username, field_name="Display name")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _validate_password_or_422(payload.password, phone=None, display_name=display_name)

    existing_user = (
        db.query(User)
        .filter(or_(User.phone == username, User.username == username))
        .first()
    )
    if existing_user:
        raise HTTPException(status_code=409, detail="Username already exists")
    if db.query(User).filter(User.display_name == display_name).first():
        raise HTTPException(status_code=409, detail="Display name already exists")

    now = utcnow()
    user = User(
        username=username,
        phone=None,
        display_name=display_name,
        display_name_key=display_name,
        hashed_password=get_password_hash(payload.password),
        role=payload.role.value,
        status=UserStatus.ACTIVE.value,
        must_change_password=False,
        password_changed_at=now,
        created_by=current_admin.id,
    )
    db.add(user)
    try:
        db.flush()
        write_auth_audit_log(
            db,
            event_type=ADMIN_USER_CREATED,
            outcome="success",
            actor_user=current_admin,
            target_user=user,
            ip_address=_request_ip(request),
            user_agent=_request_user_agent(request),
            details={"role": user.role, "status": user.status},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if db.query(User).filter(or_(User.username == username, User.phone == username)).first():
            raise HTTPException(status_code=409, detail="Username already exists") from exc
        raise HTTPException(status_code=409, detail="Display name already exists") from exc
    db.refresh(user)
    return user


@router.get("", response_model=AdminUserListResponse)
def list_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    q: Optional[str] = None,
    role: Optional[UserRole] = None,
    status: Optional[UserStatus] = None,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_super_admin),
):
    del current_admin
    query = db.query(User)
    if q:
        query = query.filter(
            or_(
                User.phone.contains(q),
                User.display_name.contains(q),
                User.username.contains(q),
            )
        )
    if role:
        query = query.filter(User.role == role.value)
    if status:
        query = query.filter(User.status == status.value)

    total = query.count()
    items = query.order_by(User.id.desc()).offset(skip).limit(limit).all()
    return AdminUserListResponse(items=[UserResponse.model_validate(item) for item in items], total=total)


@router.get("/settings/public-signup", response_model=PublicSignupSettingResponse)
def get_public_signup_setting(
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_super_admin),
):
    del current_admin
    setting = db.query(AuthSetting).filter(AuthSetting.id == 1).one()
    return PublicSignupSettingResponse(public_signup_enabled=setting.public_signup_enabled)


@router.put("/settings/public-signup", response_model=PublicSignupSettingResponse)
def update_public_signup_setting(
    payload: UpdatePublicSignupSettingRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_super_admin),
):
    setting = db.query(AuthSetting).filter(AuthSetting.id == 1).one()
    setting.public_signup_enabled = payload.public_signup_enabled
    setting.updated_by = current_admin.id
    write_auth_audit_log(
        db,
        event_type=ADMIN_PUBLIC_SIGNUP_ENABLED if payload.public_signup_enabled else ADMIN_PUBLIC_SIGNUP_DISABLED,
        actor_user=current_admin,
        ip_address=_request_ip(request),
        user_agent=_request_user_agent(request),
        details={"public_signup_enabled": payload.public_signup_enabled},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if "last active super_admin" in str(exc):
            raise HTTPException(status_code=409, detail="Cannot downgrade or disable the only super_admin") from exc
        raise
    return PublicSignupSettingResponse(public_signup_enabled=setting.public_signup_enabled)


@router.get("/{user_id}", response_model=UserResponse)
def get_user_detail(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_super_admin),
):
    del current_admin
    return _get_user_or_404(db, user_id)


@router.patch("/{user_id}/status", response_model=AdminMutationResponse)
def update_user_status(
    user_id: int,
    payload: UpdateUserStatusRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_super_admin),
):
    if payload.status not in {UserStatus.ACTIVE, UserStatus.DISABLED}:
        raise HTTPException(status_code=422, detail=STATUS_MUTATION_FORBIDDEN_MESSAGE)

    user = _get_user_or_404(db, user_id)
    _ensure_not_self_status_change(current_admin, user)
    _ensure_manageable(current_admin, user)
    _ensure_not_last_super_admin(db, user, next_status=payload.status.value)

    previous_status = user.status
    user.status = payload.status.value
    if payload.status == UserStatus.DISABLED:
        _revoke_user_sessions(db, user_id=user.id, reason="user_disabled")
    db.add(user)
    write_auth_audit_log(
        db,
        event_type=ADMIN_USER_DISABLED if payload.status == UserStatus.DISABLED else ADMIN_USER_ENABLED,
        outcome="success",
        actor_user=current_admin,
        target_user=user,
        ip_address=_request_ip(request),
        user_agent=_request_user_agent(request),
        details={"previous_status": previous_status, "next_status": user.status},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if "last active super_admin" in str(exc):
            raise HTTPException(status_code=409, detail="Cannot downgrade or disable the only super_admin") from exc
        raise
    db.refresh(user)
    return AdminMutationResponse(user=UserResponse.model_validate(user))


@router.patch("/{user_id}/role", response_model=AdminMutationResponse)
def update_user_role(
    user_id: int,
    payload: UpdateUserRoleRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_super_admin),
):
    user = _get_user_or_404(db, user_id)
    _ensure_not_self_role_change(current_admin, user)
    _ensure_manageable(current_admin, user)
    _ensure_role_assignable(current_admin, payload.role.value)
    _ensure_not_last_super_admin(db, user, next_role=payload.role.value)

    previous_role = user.role
    user.role = payload.role.value
    db.add(user)
    write_auth_audit_log(
        db,
        event_type=ADMIN_USER_ROLE_CHANGED,
        outcome="success",
        actor_user=current_admin,
        target_user=user,
        ip_address=_request_ip(request),
        user_agent=_request_user_agent(request),
        details={"previous_role": previous_role, "next_role": user.role},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if "last active super_admin" in str(exc):
            raise HTTPException(status_code=409, detail="Cannot downgrade or disable the only super_admin") from exc
        raise
    db.refresh(user)
    return AdminMutationResponse(user=UserResponse.model_validate(user))


@router.post("/{user_id}/reset-password", response_model=AdminMutationResponse)
def reset_user_password(
    user_id: int,
    payload: AdminResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_super_admin),
):
    user = _get_user_or_404(db, user_id)
    _ensure_not_self_password_reset(current_admin, user)
    _ensure_manageable(current_admin, user)
    _validate_password_or_422(payload.new_password, phone=user.phone, display_name=user.display_name)

    user.hashed_password = get_password_hash(payload.new_password)
    user.password_changed_at = utcnow()
    user.must_change_password = False
    _revoke_user_sessions(db, user_id=user.id, reason="password_reset")
    db.add(user)
    write_auth_audit_log(
        db,
        event_type=ADMIN_USER_PASSWORD_RESET,
        outcome="success",
        actor_user=current_admin,
        target_user=user,
        ip_address=_request_ip(request),
        user_agent=_request_user_agent(request),
        details={"status": user.status},
    )
    db.commit()
    db.refresh(user)
    return AdminMutationResponse(user=UserResponse.model_validate(user))
