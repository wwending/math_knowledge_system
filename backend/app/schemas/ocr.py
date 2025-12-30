from pydantic import BaseModel
from typing import Optional

# 定义响应模型：前端收到的 JSON 长这样
class OCRResponse(BaseModel):
    success: bool
    content: str       # 识别出来的 Markdown/LaTeX 文本
    cost_seconds: float
    error: Optional[str] = None