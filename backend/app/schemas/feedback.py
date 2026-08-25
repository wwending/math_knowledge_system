from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.feedback import FeedbackCategory, FeedbackStatus


class FeedbackScreenshotRead(BaseModel):
    id: int
    url: str


class FeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    content: str
    status: str
    review_note: Optional[str] = None
    screenshots: list[FeedbackScreenshotRead] = []
    created_at: datetime
    updated_at: datetime


class FeedbackAdminRead(FeedbackRead):
    user_id: int
    submitter_display_name: Optional[str] = None
    submitter_phone: Optional[str] = None


class FeedbackListResponse(BaseModel):
    items: list[FeedbackRead]
    total: int


class AdminFeedbackListResponse(BaseModel):
    items: list[FeedbackAdminRead]
    total: int


class AdminFeedbackStatusUpdate(BaseModel):
    status: FeedbackStatus
    review_note: Optional[str] = Field(default=None, max_length=500)

    @field_validator("review_note")
    @classmethod
    def normalize_review_note(cls, value: Optional[str]) -> Optional[str]:
        # 管理员留空处理说明时存 NULL，而不是空字符串。
        if value is None:
            return None
        value = value.strip()
        return value or None


class FeedbackMutationResponse(BaseModel):
    message: str
