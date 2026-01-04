from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# --- 1. 保持原有的 Tag 定义不变 ---
class Tag(BaseModel):
    label: str
    score: float

# --- 2. 抽取公共基础字段 (Base) ---
# 这些是“创建”和“返回”都共有的字段
class QuestionBase(BaseModel):
    image_url: str
    content: Optional[str] = None
    knowledge_tags: Optional[List[Tag]] = [] # 对应数据库的 JSON 字段

# --- 3. 新增：创建题目时使用的模型 (Input) ---
# 前端调用 POST /questions/ 时传这个
# 此时不需要传 id, created_at, status (默认为pending), owner_id (从token取)
class QuestionCreate(QuestionBase):
    pass 
    # 如果未来创建时有特殊参数（比如 "is_draft"），可以在这里加

# --- 4. 修改：返回题目信息的模型 (Output) ---
# 继承 Base，自动拥有 image_url 等字段，并追加数据库生成的字段
class QuestionOut(QuestionBase):
    id: int
    created_at: datetime
    
    # --- 新增字段 ---
    owner_id: int         # 必须返回，前端可能需要判断 "是不是我发的"
    status: str           # 返回状态：pending/approved/rejected

    class Config:
        # 允许 Pydantic 直接读取 SQLAlchemy 模型
        from_attributes = True