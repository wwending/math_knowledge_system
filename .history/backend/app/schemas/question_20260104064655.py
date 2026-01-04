from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import datetime

# 1. 基础 Tag 模型
class Tag(BaseModel):
    label: str
    score: float

# 2. 基础 Question 模型 (公共字段)
class QuestionBase(BaseModel):
    image_url: str
    content: Optional[str] = None
    # 这里的 Any 是为了兼容有时是 JSON 有时是 List 的情况
    knowledge_tags: Optional[Any] = []

# 3. 创建时模型 (Input)
# 前端只传 image_url, content, tags，不需要传 id, status, owner_id
class QuestionCreate(QuestionBase):
    pass

# 4. 响应模型 (Output)
# 返回给前端的数据，包含数据库生成的字段
class QuestionResponse(QuestionBase):
    id: int
    created_at: datetime
    owner_id: int
    status: str

    class Config:
        # 允许 Pydantic 直接读取 SQLAlchemy 模型
        from_attributes = True

# 5. 为了兼容 endpoints.py 的引用 (QuestionOut)
# 其实它和 QuestionResponse 是一样的，直接继承或者赋值都行
class QuestionOut(QuestionResponse):
    pass