from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.question import KnowledgeTag


class DraftCreate(BaseModel):
    source_asset_id: int
    crop_bbox: Optional[Any] = None


class DraftDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_asset_id: int
    crop_bbox: Any
    status: str
    current_content: Optional[dict[str, Any]] = None
    content: str = ""
    knowledge_tags: list[KnowledgeTag] = Field(default_factory=list)
    last_ocr_run_id: Optional[int] = None
    last_llm_run_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


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
