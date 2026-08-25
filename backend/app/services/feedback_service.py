import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, UploadFile
from loguru import logger
from PIL import Image
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.constants import (
    ALLOWED_FEEDBACK_IMAGE_MIME_TYPES,
    MAX_ASSET_SIZE_BYTES,
    MAX_FEEDBACK_SCREENSHOTS,
)
from app.core.files import resolve_upload_file_path
from app.models.feedback import (
    Feedback,
    FeedbackCategory,
    FeedbackScreenshot,
    FeedbackStatus,
)
from app.models.user import ADMIN_ROLES, User
from app.schemas.feedback import (
    AdminFeedbackListResponse,
    AdminFeedbackStatusUpdate,
    FeedbackAdminRead,
    FeedbackListResponse,
    FeedbackRead,
    FeedbackScreenshotRead,
)

# TODO(#98): 提交频率限制暂未启用（内测阶段决策）。如需防刷屏，按 user_id+自然日计数即可，
# 不要复用 login_rate_limit 表（其语义绑定登录事件）。

NOT_FOUND_MESSAGE = "资源不存在"
FEEDBACK_NOT_PENDING_MESSAGE = "已处理的反馈不能修改或撤回"
FEEDBACK_CONTENT_EMPTY_MESSAGE = "反馈内容不能为空"
FEEDBACK_SCREENSHOT_LIMIT_MESSAGE = f"最多上传 {MAX_FEEDBACK_SCREENSHOTS} 张截图"
UNSUPPORTED_IMAGE_TYPE_MESSAGE = "不支持的图片类型"
INVALID_IMAGE_FILE_MESSAGE = "无效的图片文件"
SCREENSHOT_SAVE_FAILED_MESSAGE = "截图保存失败"
FILE_TOO_LARGE_MESSAGE = "文件过大"
MISSING_FILENAME_MESSAGE = "缺少文件名"
FEEDBACK_WITHDRAWN_MESSAGE = "反馈已撤回"

CATEGORY_LABELS = {
    FeedbackCategory.BUG.value: "问题",
    FeedbackCategory.FEATURE.value: "需求",
    FeedbackCategory.SUGGESTION.value: "建议",
}
STATUS_LABELS = {
    FeedbackStatus.PENDING.value: "待处理",
    FeedbackStatus.ADOPTED.value: "已采纳",
    FeedbackStatus.REJECTED.value: "已拒绝",
}


def _safe_remove_file(path: Optional[str]) -> None:
    if not path:
        return
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError as exc:
        logger.warning("Failed to remove file {}: {}", path, exc)


def _screenshot_url(feedback_id: int, screenshot_id: int) -> str:
    # Authenticated channel only (same policy as questions/papers images, #44).
    return f"{settings.API_V1_STR}/feedback/{feedback_id}/screenshots/{screenshot_id}"


def _build_feedback_read(feedback: Feedback) -> FeedbackRead:
    return FeedbackRead(
        id=feedback.id,
        category=feedback.category,
        content=feedback.content,
        status=feedback.status,
        review_note=feedback.review_note,
        screenshots=[
            FeedbackScreenshotRead(id=shot.id, url=_screenshot_url(feedback.id, shot.id))
            for shot in (feedback.screenshots or [])
        ],
        created_at=feedback.created_at,
        updated_at=feedback.updated_at,
    )


def _build_feedback_admin_read(feedback: Feedback) -> FeedbackAdminRead:
    submitter = feedback.user
    return FeedbackAdminRead(
        **_build_feedback_read(feedback).model_dump(),
        user_id=feedback.user_id,
        submitter_display_name=submitter.display_name if submitter else None,
        submitter_phone=submitter.phone if submitter else None,
    )


def _store_screenshot(upload: UploadFile) -> str:
    """Persist one feedback screenshot into UPLOAD_DIR; return the bare filename.

    Mirrors the upload_asset flow (MIME whitelist -> uuid-prefixed basename ->
    streamed size-capped write -> PIL integrity check) minus the sha256 column:
    feedback screenshots are private evidence files and never deduplicate.
    """
    if not upload.filename:
        raise HTTPException(status_code=400, detail=MISSING_FILENAME_MESSAGE)
    mime = upload.content_type or ""
    if mime not in ALLOWED_FEEDBACK_IMAGE_MIME_TYPES:
        raise HTTPException(status_code=400, detail=UNSUPPORTED_IMAGE_TYPE_MESSAGE)

    original_name = os.path.basename(upload.filename)
    if not original_name:
        raise HTTPException(status_code=400, detail=MISSING_FILENAME_MESSAGE)

    stored_filename = f"{uuid.uuid4().hex}_{original_name}"
    file_path = str(settings.UPLOAD_DIR_PATH / stored_filename)

    try:
        size_bytes = 0
        with open(file_path, "wb") as buffer:
            while True:
                chunk = upload.file.read(1024 * 1024)
                if not chunk:
                    break
                size_bytes += len(chunk)
                if size_bytes > MAX_ASSET_SIZE_BYTES:
                    raise HTTPException(status_code=413, detail=FILE_TOO_LARGE_MESSAGE)
                buffer.write(chunk)
    except HTTPException:
        _safe_remove_file(file_path)
        raise
    except OSError:
        logger.exception("Failed to save feedback screenshot path={}", file_path)
        _safe_remove_file(file_path)
        raise HTTPException(status_code=500, detail=SCREENSHOT_SAVE_FAILED_MESSAGE)
    finally:
        try:
            upload.file.close()
        except Exception:
            pass

    try:
        with Image.open(file_path) as img:
            img.verify()
    except Exception:
        _safe_remove_file(file_path)
        raise HTTPException(status_code=400, detail=INVALID_IMAGE_FILE_MESSAGE)

    return stored_filename


def _store_screenshots(uploads: list[UploadFile]) -> list[str]:
    """Store every upload; on any failure remove the already-written files."""
    stored_names: list[str] = []
    try:
        for upload in uploads:
            stored_names.append(_store_screenshot(upload))
    except Exception:
        for name in stored_names:
            _safe_remove_file(str(settings.UPLOAD_DIR_PATH / name))
        raise
    return stored_names


def _discard_stored_files(stored_names: list[str]) -> None:
    for name in stored_names:
        _safe_remove_file(str(settings.UPLOAD_DIR_PATH / name))


def _get_own_feedback_or_404(db: Session, current_user: User, feedback_id: int) -> Feedback:
    feedback = (
        db.query(Feedback)
        .filter(Feedback.id == feedback_id, Feedback.user_id == current_user.id)
        .first()
    )
    if not feedback:
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)
    return feedback


def _ensure_pending(feedback: Feedback) -> None:
    if feedback.status != FeedbackStatus.PENDING.value:
        raise HTTPException(status_code=409, detail=FEEDBACK_NOT_PENDING_MESSAGE)


def create_feedback(
    db: Session,
    current_user: User,
    *,
    content: str,
    category: FeedbackCategory,
    screenshot_uploads: Optional[list[UploadFile]],
) -> FeedbackRead:
    cleaned = (content or "").strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail=FEEDBACK_CONTENT_EMPTY_MESSAGE)

    uploads = [upload for upload in (screenshot_uploads or []) if upload is not None]
    if len(uploads) > MAX_FEEDBACK_SCREENSHOTS:
        raise HTTPException(status_code=400, detail=FEEDBACK_SCREENSHOT_LIMIT_MESSAGE)

    stored_names = _store_screenshots(uploads)

    feedback = Feedback(
        user_id=current_user.id,
        category=category.value,
        content=cleaned,
        status=FeedbackStatus.PENDING.value,
    )
    try:
        db.add(feedback)
        db.flush()
        for name in stored_names:
            db.add(FeedbackScreenshot(feedback_id=feedback.id, path=name))
        db.commit()
    except Exception:
        db.rollback()
        _discard_stored_files(stored_names)
        raise

    db.refresh(feedback)
    return _build_feedback_read(feedback)


def list_own_feedback(
    db: Session,
    current_user: User,
    *,
    skip: int,
    limit: int,
    category: Optional[FeedbackCategory],
    status: Optional[FeedbackStatus],
) -> FeedbackListResponse:
    query = db.query(Feedback).filter(Feedback.user_id == current_user.id)
    if category:
        query = query.filter(Feedback.category == category.value)
    if status:
        query = query.filter(Feedback.status == status.value)

    total = query.count()
    items = (
        query.options(joinedload(Feedback.screenshots))
        .order_by(Feedback.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return FeedbackListResponse(
        items=[_build_feedback_read(feedback) for feedback in items],
        total=total,
    )


def update_own_feedback(
    db: Session,
    current_user: User,
    feedback_id: int,
    *,
    content: Optional[str],
    category: Optional[FeedbackCategory],
    new_screenshot_uploads: Optional[list[UploadFile]],
    remove_screenshot_ids_raw: str,
) -> FeedbackRead:
    feedback = _get_own_feedback_or_404(db, current_user, feedback_id)
    _ensure_pending(feedback)

    cleaned_content: Optional[str] = None
    if content is not None:
        cleaned_content = content.strip()
        if not cleaned_content:
            raise HTTPException(status_code=400, detail=FEEDBACK_CONTENT_EMPTY_MESSAGE)

    existing = list(feedback.screenshots or [])
    existing_by_id = {shot.id: shot for shot in existing}

    # remove_screenshot_ids semantics (#98): comma-separated ids to delete.
    # Unknown ids and malformed segments are silently ignored so a tampered
    # request cannot probe which screenshot ids exist on someone else's row.
    seen_ids: set[int] = set()
    remove_targets: list[FeedbackScreenshot] = []
    for part in (remove_screenshot_ids_raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            shot_id = int(part)
        except ValueError:
            continue
        if shot_id in seen_ids:
            continue
        target = existing_by_id.get(shot_id)
        if target is None:
            continue
        seen_ids.add(shot_id)
        remove_targets.append(target)

    uploads = [upload for upload in (new_screenshot_uploads or []) if upload is not None]
    remaining_count = len(existing) - len(remove_targets)
    if remaining_count + len(uploads) > MAX_FEEDBACK_SCREENSHOTS:
        raise HTTPException(status_code=400, detail=FEEDBACK_SCREENSHOT_LIMIT_MESSAGE)

    # Files hit disk first; the DB swap commits second; stale files leave last
    # (never delete before the commit that stops referencing them).
    stored_names = _store_screenshots(uploads)
    removed_paths = [target.path for target in remove_targets]
    try:
        if cleaned_content is not None:
            feedback.content = cleaned_content
        if category is not None:
            feedback.category = category.value
        for target in remove_targets:
            db.delete(target)
        for name in stored_names:
            db.add(FeedbackScreenshot(feedback_id=feedback.id, path=name))
        db.commit()
    except Exception:
        db.rollback()
        _discard_stored_files(stored_names)
        raise

    for relative_path in removed_paths:
        _safe_remove_file(resolve_upload_file_path(relative_path))

    db.refresh(feedback)
    return _build_feedback_read(feedback)


def withdraw_feedback(db: Session, current_user: User, feedback_id: int) -> str:
    """Delete own pending feedback together with its screenshot files."""
    feedback = _get_own_feedback_or_404(db, current_user, feedback_id)
    _ensure_pending(feedback)

    screenshot_paths = [
        resolve_upload_file_path(shot.path) for shot in (feedback.screenshots or [])
    ]
    try:
        db.delete(feedback)
        db.commit()
    except Exception:
        db.rollback()
        raise

    for resolved_path in screenshot_paths:
        _safe_remove_file(resolved_path)
    return FEEDBACK_WITHDRAWN_MESSAGE


def get_screenshot_file_path_or_404(
    db: Session,
    current_user: User,
    feedback_id: int,
    screenshot_id: int,
) -> str:
    # Papers-domain privacy convention (#59): missing feedback, a foreign row,
    # a screenshot from another row, and an unresolvable file all answer 404 —
    # except that admins may inspect every submission.
    query = db.query(Feedback).filter(Feedback.id == feedback_id)
    if current_user.role not in ADMIN_ROLES:
        query = query.filter(Feedback.user_id == current_user.id)
    feedback = query.first()
    if not feedback:
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)

    target = next((shot for shot in (feedback.screenshots or []) if shot.id == screenshot_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)

    file_path = resolve_upload_file_path(target.path)
    if not file_path:
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)
    return file_path


def admin_list_feedback(
    db: Session,
    *,
    q: Optional[str],
    category: Optional[FeedbackCategory],
    status: Optional[FeedbackStatus],
    skip: int,
    limit: int,
) -> AdminFeedbackListResponse:
    query = db.query(Feedback).options(joinedload(Feedback.user))
    if q:
        query = query.join(User, Feedback.user_id == User.id).filter(
            or_(
                Feedback.content.contains(q),
                User.display_name.contains(q),
                User.phone.contains(q),
            )
        )
    if category:
        query = query.filter(Feedback.category == category.value)
    if status:
        query = query.filter(Feedback.status == status.value)

    total = query.count()
    items = (
        query.order_by(Feedback.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return AdminFeedbackListResponse(
        items=[_build_feedback_admin_read(feedback) for feedback in items],
        total=total,
    )


def admin_set_feedback_status(
    db: Session,
    feedback_id: int,
    payload: AdminFeedbackStatusUpdate,
) -> FeedbackAdminRead:
    """Set status directly — transitions among pending/adopted/rejected are free
    so an admin can correct mistakes (e.g. rejected -> adopted); updated_at
    records the latest change."""
    feedback = (
        db.query(Feedback)
        .options(joinedload(Feedback.user), joinedload(Feedback.screenshots))
        .filter(Feedback.id == feedback_id)
        .first()
    )
    if not feedback:
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)

    feedback.status = payload.status.value
    feedback.review_note = payload.review_note
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(feedback)
    return _build_feedback_admin_read(feedback)


def collect_export_items(db: Session, *, status: FeedbackStatus) -> list[dict]:
    """Rows for the codex workflow (#98): absolute server paths included so the
    deployment host can read screenshot bytes directly."""
    rows = (
        db.query(Feedback)
        .options(joinedload(Feedback.user), joinedload(Feedback.screenshots))
        .filter(Feedback.status == status.value)
        .order_by(Feedback.id.asc())
        .all()
    )
    items: list[dict] = []
    for feedback in rows:
        submitter = feedback.user
        items.append(
            {
                "id": feedback.id,
                "category": feedback.category,
                "content": feedback.content,
                "status": feedback.status,
                "review_note": feedback.review_note,
                "submitter": {
                    "display_name": submitter.display_name if submitter else None,
                    "phone": submitter.phone if submitter else None,
                },
                "created_at": feedback.created_at.isoformat() if feedback.created_at else None,
                "updated_at": feedback.updated_at.isoformat() if feedback.updated_at else None,
                "screenshot_files": [
                    resolved
                    for resolved in (
                        resolve_upload_file_path(shot.path)
                        for shot in (feedback.screenshots or [])
                    )
                    if resolved
                ],
            }
        )
    return items


def build_markdown_export(items: list[dict], *, status_value: str) -> str:
    exported_text = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        f"# 用户反馈导出（status={status_value}）",
        "",
        f"导出时间：{exported_text} · 共 {len(items)} 条 · format=markdown",
        "",
    ]
    for item in items:
        category_label = CATEGORY_LABELS.get(item["category"], item["category"])
        status_label = STATUS_LABELS.get(item["status"], item["status"])
        submitter = item["submitter"]
        submitter_text = "{}（{}）".format(
            submitter.get("display_name") or "", submitter.get("phone") or ""
        )
        screenshots_text = (
            "；".join(item["screenshot_files"]) if item["screenshot_files"] else "（无）"
        )
        review_note_text = item["review_note"] or "（无）"
        created_text = (item["created_at"] or "").replace("T", " ")[:19]
        quoted_content = "\n".join(
            f"> {line}" for line in item["content"].splitlines() or [item["content"]]
        )
        lines.extend(
            [
                f"## #{item['id']} [{category_label}] 提交于 {created_text}",
                "",
                f"- 提交者：{submitter_text}",
                f"- 状态：{status_label}",
                f"- 处理说明：{review_note_text}",
                f"- 截图文件：{screenshots_text}",
                "",
                "内容：",
                "",
                quoted_content,
                "",
                "---",
                "",
            ]
        )
    return "\n".join(lines)
