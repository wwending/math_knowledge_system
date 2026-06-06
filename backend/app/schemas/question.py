from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeTag(BaseModel):
    label: str
    score: float = 1.0


class Tag(KnowledgeTag):
    pass


class QuestionUpdate(BaseModel):
    content: str


class QuestionListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: Optional[str] = None
    knowledge_tags: list[KnowledgeTag] = Field(default_factory=list)
    question_type: Optional[str] = None
    difficulty_level: Optional[int] = None
    difficulty_label: Optional[str] = None
    difficulty_confidence: Optional[float] = None
    difficulty_reason: Optional[str] = None
    difficulty_model: Optional[str] = None
    difficulty_evaluated_at: Optional[datetime] = None
    metadata_status: Optional[str] = None
    metadata_error: Optional[str] = None
    metadata_started_at: Optional[datetime] = None
    metadata_finished_at: Optional[datetime] = None
    origin_image: Optional[str] = None
    image_url: Optional[str] = None
    created_at: Optional[datetime] = None


class QuestionDetail(QuestionListItem):
    pass


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    image_url: Optional[str] = None
    content: Optional[str] = None
    knowledge_tags: list[Tag] = Field(default_factory=list)
    question_type: Optional[str] = None
    difficulty_level: Optional[int] = None
    difficulty_label: Optional[str] = None
    difficulty_confidence: Optional[float] = None
    difficulty_reason: Optional[str] = None
    difficulty_model: Optional[str] = None
    difficulty_evaluated_at: Optional[datetime] = None
    metadata_status: Optional[str] = None
    metadata_error: Optional[str] = None
    metadata_started_at: Optional[datetime] = None
    metadata_finished_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
