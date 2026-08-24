from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.question import KnowledgeTag


class DraftCreate(BaseModel):
    source_asset_id: int
    crop_bbox: Optional[Any] = None


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
    """Optional body for save-to-bank (#58).

    figure_bbox is the user-confirmed figure region ([x, y, w, h] normalized).
    Absent/None means the question has no figure; an invalid value is ignored.
    """

    figure_bbox: Optional[list[float]] = None


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
