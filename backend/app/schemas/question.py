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
    created_at: Optional[datetime] = None
