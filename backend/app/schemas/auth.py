from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.models.user import UserRole, UserStatus


class LoginRequest(BaseModel):
    username: str = Field(validation_alias=AliasChoices("username", "phone"))
    password: str


class AuthCapabilitiesResponse(BaseModel):
    public_signup_enabled: bool
    password_recovery_mode: str
    sms_code_login_enabled: bool
    sms_password_recovery_enabled: bool


class RefreshRequest(BaseModel):
    refresh_token: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class RegisterRequest(BaseModel):
    username: str
    display_name: Optional[str] = None
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    phone: Optional[str]
    username: Optional[str]
    display_name: str
    role: str
    status: str
    must_change_password: bool
    last_login_at: Optional[datetime]
    password_changed_at: Optional[datetime]
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime
    phone_verified_at: Optional[datetime]


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class LogoutResponse(BaseModel):
    success: bool = True


class ChangePasswordResponse(BaseModel):
    success: bool = True
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class AdminCreateUserRequest(BaseModel):
    username: str
    display_name: Optional[str] = None
    password: str
    role: UserRole = UserRole.USER


class AdminUserListResponse(BaseModel):
    items: list[UserResponse]
    total: int


class UpdateUserStatusRequest(BaseModel):
    status: UserStatus


class UpdateUserRoleRequest(BaseModel):
    role: UserRole


class AdminResetPasswordRequest(BaseModel):
    new_password: str


class PublicSignupSettingResponse(BaseModel):
    public_signup_enabled: bool


class UpdatePublicSignupSettingRequest(BaseModel):
    public_signup_enabled: bool


class AdminMutationResponse(BaseModel):
    success: bool = True
    user: UserResponse
