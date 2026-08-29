from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.question import KnowledgeTag
from app.services.draft_image_service import normalize_draft_bbox


class DraftCreate(BaseModel):
    source_asset_id: int
    crop_bbox: list[float] | dict[str, Any] = Field(default_factory=dict)

    @field_validator("crop_bbox", mode="before")
    @classmethod
    def validate_crop_bbox(cls, value: Any) -> list[float] | dict[str, Any]:
        return normalize_draft_bbox(value)


class DraftUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=100_000)


class RecognitionDebug(BaseModel):
    ocr_provider: Optional[str] = None
    ocr_raw_text: Optional[str] = None
    llm_cleaned_text: Optional[str] = None
    ocr_error: Optional[str] = None
    llm_error: Optional[str] = None


class RecognitionQualityWarning(BaseModel):
    code: str
    level: str = "warning"
    message: str


class FigureDetection(BaseModel):
    """One figure region detected in the draft asset (#58)."""

    bbox: list[float]  # [x, y, w, h] normalized to [0, 1]
    label: Optional[str] = None
    score: Optional[float] = None


class DraftDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_asset_id: int
    crop_bbox: Any
    detected_figures: list[FigureDetection] = Field(default_factory=list)
    status: str
    current_content: Optional[dict[str, Any]] = None
    content: str = ""
    knowledge_tags: list[KnowledgeTag] = Field(default_factory=list)
    question_type: Optional[str] = None
    difficulty_level: Optional[int] = None
    difficulty_label: Optional[str] = None
    difficulty_confidence: Optional[float] = None
    difficulty_reason: Optional[str] = None
    last_ocr_run_id: Optional[int] = None
    last_llm_run_id: Optional[int] = None
    recognition_debug: Optional[RecognitionDebug] = None
    quality_warnings: list[RecognitionQualityWarning] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DraftSaveToBankRequest(BaseModel):
    """Optional figure confirmation body for save-to-bank (#129).

    ``figure_bboxes`` is the public plural contract. ``figure_bbox`` remains a
    temporary compatibility input for older clients; callers must not send both.
    """

    figure_bboxes: Optional[list[list[float]]] = None
    figure_bbox: Optional[list[float]] = None

    @model_validator(mode="after")
    def reject_ambiguous_figure_fields(self) -> "DraftSaveToBankRequest":
        if {"figure_bboxes", "figure_bbox"}.issubset(self.model_fields_set):
            raise ValueError("figure_bboxes and figure_bbox cannot both be provided")
        return self

    def resolved_figure_bboxes(self) -> list[list[float]]:
        if "figure_bboxes" in self.model_fields_set:
            return self.figure_bboxes or []
        if "figure_bbox" in self.model_fields_set and self.figure_bbox is not None:
            return [self.figure_bbox]
        return []


class DraftRecognizeResponse(DraftDetail):
    success: bool
    partial_success: bool = False
    warning: Optional[str] = None
    error: Optional[str] = None
    error_type: Optional[str] = None


class DraftSaveToBankResponse(DraftDetail):
    question_id: int
    question_revision_id: int
    rev_no: int
