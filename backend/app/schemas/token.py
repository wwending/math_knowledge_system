from pydantic import BaseModel
from typing import Optional

# 这是为了告诉前端：登录接口返回的数据长什么样
class Token(BaseModel):
    access_token: str
    token_type: str

# 这是给 JWT 解析用的 (暂时用不到，但为了完整性先加上)
class TokenPayload(BaseModel):
    sub: Optional[str] = None