from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.question import KnowledgeTag


class OCRResponse(BaseModel):
    success: bool
    content: str
    knowledge: list[KnowledgeTag] = Field(default_factory=list)
    cost_seconds: float
    image_url: Optional[str] = None
    id: int
    created_at: Optional[datetime] = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    partial_success: bool = False
    warning: Optional[str] = None
