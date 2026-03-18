from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import ExpiredSignatureError, JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import User


LOGIN_REQUIRED_MESSAGE = "\u8bf7\u5148\u767b\u5f55"
INVALID_TOKEN_MESSAGE = "\u767b\u5f55\u72b6\u6001\u65e0\u6548\uff0c\u8bf7\u91cd\u65b0\u767b\u5f55"
EXPIRED_TOKEN_MESSAGE = "\u767b\u5f55\u5df2\u8fc7\u671f\uff0c\u8bf7\u91cd\u65b0\u767b\u5f55"
BAD_CREDENTIALS_MESSAGE = "\u7528\u6237\u540d\u6216\u5bc6\u7801\u9519\u8bef"
DISABLED_USER_MESSAGE = "\u8d26\u6237\u5df2\u88ab\u7981\u7528"
ADMIN_REQUIRED_MESSAGE = "\u9700\u8981\u7ba1\u7406\u5458\u6743\u9650"


router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/token",
    auto_error=False,
)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterIn(BaseModel):
    username: str
    password: str
    email: Optional[str] = None


class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    role: str
    is_active: bool

    class Config:
        from_attributes = True


def _get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username).first()


def _raise_auth_error(detail: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/register", response_model=UserOut)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    if _get_user_by_username(db, payload.username):
        raise HTTPException(status_code=409, detail="\u7528\u6237\u540d\u5df2\u5b58\u5728")

    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        role="user",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/token", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = _get_user_by_username(db, form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        _raise_auth_error(BAD_CREDENTIALS_MESSAGE)
    if not user.is_active:
        raise HTTPException(status_code=403, detail=DISABLED_USER_MESSAGE)

    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return Token(access_token=access_token)


def get_current_user(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme),
) -> User:
    if not token:
        _raise_auth_error(LOGIN_REQUIRED_MESSAGE)

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("sub")
        if not username:
            _raise_auth_error(INVALID_TOKEN_MESSAGE)
    except ExpiredSignatureError:
        _raise_auth_error(EXPIRED_TOKEN_MESSAGE)
    except JWTError:
        _raise_auth_error(INVALID_TOKEN_MESSAGE)

    user = _get_user_by_username(db, username)
    if not user:
        _raise_auth_error(INVALID_TOKEN_MESSAGE)
    if not user.is_active:
        raise HTTPException(status_code=403, detail=DISABLED_USER_MESSAGE)
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail=ADMIN_REQUIRED_MESSAGE)
    return user


@router.get("/me", response_model=UserOut)
def read_me(user: User = Depends(get_current_user)):
    return user
