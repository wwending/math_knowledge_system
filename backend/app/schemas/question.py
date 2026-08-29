from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class KnowledgeTag(BaseModel):
    label: str
    score: float = 1.0


class Tag(KnowledgeTag):
    pass


class QuestionUpdate(BaseModel):
    content: Optional[str] = Field(None, min_length=1, max_length=20000)
    answer: Optional[str] = None
    analysis: Optional[str] = None
    knowledge_tags: Optional[list[KnowledgeTag]] = None
    question_type: Optional[str] = None
    difficulty_level: Optional[int] = Field(None, ge=1, le=5)
    expected_revision_no: Optional[int] = Field(None, ge=1)



class QuestionListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: Optional[str] = None
    answer: Optional[str] = None
    analysis: Optional[str] = None
    current_revision_no: Optional[int] = None
    schema_version: int = 2
    has_question_image: bool = False
    has_figure: bool = False
    deleted_at: Optional[datetime] = None
    purge_at: Optional[datetime] = None
    purged_at: Optional[datetime] = None
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


class QuestionFigureInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: str
    crop_bbox: Optional[list[float]] = None


class QuestionDocumentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    knowledge_tags: list[KnowledgeTag] = Field(default_factory=list)
    question_type: Optional[str] = None
    difficulty_level: Optional[int] = Field(None, ge=1, le=5)


class QuestionDocumentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int
    expected_revision_no: int = Field(ge=0)
    sections: dict[str, Any]
    figures: list[QuestionFigureInput] = Field(default_factory=list)
    metadata: QuestionDocumentMetadata


class QuestionFigureDetail(BaseModel):
    id: str
    url: str
    mime: str
    size_bytes: int
    width: Optional[int] = None
    height: Optional[int] = None
    source_crop_bbox: list[float]


class QuestionDocumentDetail(BaseModel):
    id: int
    schema_version: int = 2
    current_revision_no: int
    sections: dict[str, Any]
    figures: list[QuestionFigureDetail]
    content: Optional[str] = None
    answer: Optional[str] = None
    analysis: Optional[str] = None
    knowledge_tags: list[KnowledgeTag] = Field(default_factory=list)
    question_type: Optional[str] = None
    difficulty_level: Optional[int] = None
    has_question_image: bool
    has_figure: bool
    image_url: Optional[str] = None


class QuestionDocumentUpdateResponse(BaseModel):
    success: bool = True
    revision_created: bool
    current_revision_no: int
    question: QuestionDocumentDetail


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
