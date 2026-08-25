from datetime import datetime, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.api.v1.auth import require_active_user, require_admin
from app.core.database import get_db
from app.models.feedback import FeedbackCategory, FeedbackStatus
from app.models.user import User
from app.schemas.feedback import (
    AdminFeedbackListResponse,
    AdminFeedbackStatusUpdate,
    FeedbackAdminRead,
    FeedbackListResponse,
    FeedbackMutationResponse,
    FeedbackRead,
)
from app.services import feedback_service


router = APIRouter(prefix="/feedback", tags=["feedback"])
admin_router = APIRouter(prefix="/admin/feedback", tags=["admin-feedback"])


@router.post("", response_model=FeedbackRead)
def create_feedback_endpoint(
    content: str = Form(min_length=1, max_length=500),
    category: FeedbackCategory = Form(...),
    screenshots: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    return feedback_service.create_feedback(
        db,
        current_user,
        content=content,
        category=category,
        screenshot_uploads=screenshots,
    )


@router.get("", response_model=FeedbackListResponse)
def list_own_feedback_endpoint(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    category: Optional[FeedbackCategory] = None,
    status: Optional[FeedbackStatus] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    return feedback_service.list_own_feedback(
        db,
        current_user,
        skip=skip,
        limit=limit,
        category=category,
        status=status,
    )


@router.patch("/{feedback_id}", response_model=FeedbackRead)
def update_own_feedback_endpoint(
    feedback_id: int,
    content: Optional[str] = Form(None, max_length=500),
    category: Optional[FeedbackCategory] = Form(None),
    new_screenshots: Optional[List[UploadFile]] = File(None),
    remove_screenshot_ids: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    return feedback_service.update_own_feedback(
        db,
        current_user,
        feedback_id,
        content=content,
        category=category,
        new_screenshot_uploads=new_screenshots,
        remove_screenshot_ids_raw=remove_screenshot_ids,
    )


@router.delete("/{feedback_id}", response_model=FeedbackMutationResponse)
def withdraw_feedback_endpoint(
    feedback_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    message = feedback_service.withdraw_feedback(db, current_user, feedback_id)
    return FeedbackMutationResponse(message=message)


@router.get("/{feedback_id}/screenshots/{screenshot_id}")
def get_feedback_screenshot_endpoint(
    feedback_id: int,
    screenshot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    # Authenticated image channel (#44): no public static URL ever exposes
    # feedback screenshots; admins may inspect every submission.
    file_path = feedback_service.get_screenshot_file_path_or_404(
        db, current_user, feedback_id, screenshot_id
    )
    return FileResponse(file_path)


@admin_router.get("/export")
def export_feedback_endpoint(
    export_format: Literal["markdown", "json"] = Query(default="markdown", alias="format"),
    status: FeedbackStatus = Query(default=FeedbackStatus.PENDING),
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    del current_admin
    items = feedback_service.collect_export_items(db, status=status)
    if export_format == "json":
        return {
            "status": status.value,
            "count": len(items),
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "items": items,
        }
    markdown_text = feedback_service.build_markdown_export(items, status_value=status.value)
    return Response(content=markdown_text, media_type="text/markdown; charset=utf-8")


@admin_router.get("", response_model=AdminFeedbackListResponse)
def admin_list_feedback_endpoint(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    q: Optional[str] = None,
    category: Optional[FeedbackCategory] = None,
    status: Optional[FeedbackStatus] = None,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    del current_admin
    return feedback_service.admin_list_feedback(
        db,
        q=q,
        category=category,
        status=status,
        skip=skip,
        limit=limit,
    )


@admin_router.patch("/{feedback_id}/status", response_model=FeedbackAdminRead)
def admin_set_feedback_status_endpoint(
    feedback_id: int,
    payload: AdminFeedbackStatusUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    del current_admin
    return feedback_service.admin_set_feedback_status(db, feedback_id, payload)
