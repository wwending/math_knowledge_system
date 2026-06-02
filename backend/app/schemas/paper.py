from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class PaperItemCreate(BaseModel):
    question_id: int
    score: Optional[float] = None


class PaperCreate(BaseModel):
    title: str
    description: Optional[str] = None
    items: list[PaperItemCreate]


class PaperItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question_id: int
    position: int
    score: Optional[float] = None
    content_snapshot: str
    answer_snapshot: Optional[str] = None
    analysis_snapshot: Optional[str] = None
    knowledge_tags_snapshot: Optional[list[Any]] = None


class PaperRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str] = None
    status: str
    item_count: int
    total_score: float
    items: list[PaperItemRead]
    created_at: datetime
    updated_at: datetime


class PaperListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: str
    item_count: int
    total_score: float
    created_at: datetime
    updated_at: datetime
