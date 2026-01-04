from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from typing import Optional

# --- 内部模块引入 ---
from app.core.database import get_db
from app.models.user import User
from app.core.security import SECRET_KEY, ALGORITHM # 确保你的 security.py 里有这两个变量

# 1. 定义 OAuth2 认证方案
# tokenUrl 必须指向你的登录接口路径 (POST /api/v1/auth/token)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/token")

# 2. 核心依赖函数：获取当前用户
async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # 解码 JWT Token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    # 从数据库查找用户
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
        
    return user