from pydantic import BaseModel
from typing import Optional, List, Dict, Any

# 定义单个知识点预测的结构 (Label + Score)
class KnowledgePrediction(BaseModel):
    label: str
    score: float

class OCRResponse(BaseModel):
    success: bool
    content: str
    # 新增字段：知识点列表，默认为空
    knowledge: List[KnowledgePrediction] = []
    cost_seconds: float
    error: Optional[str] = None