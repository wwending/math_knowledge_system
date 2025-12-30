from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# 单个知识点标签结构
class Tag(BaseModel):
    label: str
    score: float

# 题目信息的返回模型
class QuestionOut(BaseModel):
    id: int
    image_url: str
    content: Optional[str] = None
    knowledge_tags: Optional[List[Tag]] = [] # 读取 JSON
    created_at: datetime

    class Config:
        # 允许 Pydantic 直接读取 SQLAlchemy 模型
        from_attributes = True