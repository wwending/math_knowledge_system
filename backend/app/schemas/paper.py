from datetime import datetime
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PaperItemCreate(BaseModel):
    question_id: int
    score: Optional[float] = None


class PaperCreate(BaseModel):
    title: str
    description: Optional[str] = None
    items: list[PaperItemCreate]


def _validate_non_empty_snapshot(value: Optional[str]) -> Optional[str]:
    if value is None or not value.strip():
        raise ValueError("题干不能为空")
    return value


class PaperExistingItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["existing"]
    id: int
    question_id: int
    score: float = Field(default=0, ge=0, allow_inf_nan=False)


class PaperQuestionItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["question"]
    question_id: int
    score: float = Field(default=0, ge=0, allow_inf_nan=False)


PaperItemUpdate = Annotated[
    Union[PaperExistingItemUpdate, PaperQuestionItemUpdate],
    Field(discriminator="kind"),
]


class PaperUpdate(BaseModel):
    title: str = Field(max_length=80)
    description: Optional[str] = Field(default=None, max_length=300)
    show_answer: Optional[bool] = None
    show_analysis: Optional[bool] = None
    items: list[PaperItemUpdate] = Field(min_length=1)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("试卷标题不能为空")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None


class PaperItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question_id: int
    position: int
    score: Optional[float] = None
    content_snapshot: str
    answer_snapshot: Optional[str] = None
    analysis_snapshot: Optional[str] = None
    section_snapshot: Optional[dict[str, Any]] = None
    knowledge_tags_snapshot: Optional[list[Any]] = None
    question_type_snapshot: Optional[str] = None
    difficulty_level_snapshot: Optional[int] = None
    difficulty_label_snapshot: Optional[str] = None
    figure_image_snapshot: Optional[str] = None
    figure_ids: list[str] = Field(default_factory=list)


class PaperRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str] = None
    status: str
    show_answer: bool
    show_analysis: bool
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
