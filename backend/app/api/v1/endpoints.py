import hashlib
import json
import mimetypes
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional
from urllib.parse import quote

import fitz
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from loguru import logger
from PIL import Image
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.auth import require_active_user
from app.core.config import settings
from app.core.constants import (
    ALLOWED_ASSET_MIME_TYPES,
    MAX_ASSET_SIZE_BYTES,
    MAX_PDF_PAGES,
    PDF_TEMP_TTL_SECONDS,
    DraftEventType,
    DraftStatus,
)
from app.core.database import get_db
from app.core.files import resolve_upload_file_path
from app.models.draft import Draft
from app.models.draft_event import DraftEvent
from app.models.llm_run import LLMRun
from app.models.ocr_run import OCRRun
from app.models.paper import Paper
from app.models.question import Question
from app.models.question_revision import QuestionRevision
from app.models.source_asset import SourceAsset
from app.models.user import User
from app.schemas.draft import (
    DraftCreate,
    DraftDetail,
    DraftRecognizeResponse,
    DraftSaveToBankRequest,
    DraftSaveToBankResponse,
    DraftUpdate,
    FigureDetection,
    RecognitionDebug,
)
from app.schemas.ocr import OCRResponse
from app.schemas.paper import PaperCreate, PaperListItem, PaperRead, PaperUpdate
from app.schemas.paper_render import PaperRenderItem, PaperRenderModel, PaperRenderRequest
from app.schemas.question import KnowledgeTag, QuestionDetail, QuestionListItem, QuestionUpdate
from app.services.draft_image_service import (
    compose_bbox_to_page,
    create_cropped_temp_image,
    render_draft_image,
)
from app.services.draft_state import transition_draft_status
from app.services.llm import nlp_service
from app.services.layout_service import layout_service, remove_quiet, write_masked_image
from app.services.ocr_engine import ocr_service
from app.services.ocr_providers.base import OCRResult
from app.services.ocr_service import ocr_service as draft_ocr_service
from app.services.paper_service import create_paper, get_paper, list_papers, update_paper
from app.services.question_service import update as update_question_service, trash as trash_question, restore as restore_question, permanent as permanent_question, latest as latest_question_revision
from app.services.paper_render_service import build_paper_render_model, resolve_paper_figure_files
from app.services.paper_html_renderer import (
    PaperFigureTooLargeError,
    PaperHtmlRenderError,
    render_paper_html,
)
from app.services.pdf_generation_service import GotenbergPdfGenerationService, PdfGenerationError, PdfGenerationOptions
from app.services.question_metadata import evaluate_question_metadata_task
from app.services.recognition_quality import detect_quality_warnings


router = APIRouter()

pdf_generation_service = GotenbergPdfGenerationService(
    settings.PDF_SERVICE_URL,
    settings.PDF_SERVICE_CONNECT_TIMEOUT_SECONDS,
    settings.PDF_SERVICE_READ_TIMEOUT_SECONDS,
)

NOT_FOUND_MESSAGE = "\u8d44\u6e90\u4e0d\u5b58\u5728"
FORBIDDEN_MESSAGE = "\u65e0\u6743\u8bbf\u95ee\u8be5\u8d44\u6e90"
QUESTION_UPDATED_MESSAGE = "\u9898\u76ee\u5185\u5bb9\u5df2\u66f4\u65b0"
PDF_ONLY_MESSAGE = "\u8bf7\u4e0a\u4f20 PDF \u6587\u4ef6"
PDF_PARSE_FAILED_MESSAGE = "\u672a\u80fd\u89e3\u6790 PDF \u6587\u4ef6"
PDF_TOO_MANY_PAGES_MESSAGE = "PDF \u9875\u6570\u8d85\u8fc7\u4e0a\u9650"
PDF_GENERATION_UNAVAILABLE_MESSAGE = "PDF \u751f\u6210\u670d\u52a1\u6682\u65f6\u4e0d\u53ef\u7528\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5"
PDF_PAPER_TOO_LARGE_MESSAGE = "\u8bd5\u5377\u5185\u5bb9\u8fc7\u5927\uff0c\u65e0\u6cd5\u751f\u6210 PDF"
UPLOAD_SAVE_FAILED_MESSAGE = "\u4e0a\u4f20\u6587\u4ef6\u4fdd\u5b58\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5"
QUESTION_SAVE_FAILED_MESSAGE = "\u9898\u76ee\u4fdd\u5b58\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5"
DRAFT_READY_REQUIRED_MESSAGE = "\u53ea\u6709\u5df2\u8bc6\u522b\u5b8c\u6210\u7684 Draft \u53ef\u4ee5\u4fdd\u5b58\u5165\u9898\u5e93"
DRAFT_ALREADY_SAVED_MESSAGE = "\u5df2\u4fdd\u5b58\u5165\u9898\u5e93\u7684 Draft \u4e0d\u80fd\u91cd\u590d\u4fdd\u5b58"
DRAFT_ALREADY_SAVED_RECOGNIZE_MESSAGE = "\u5df2\u4fdd\u5b58\u5165\u9898\u5e93\u7684 Draft \u4e0d\u80fd\u518d\u6b21\u8bc6\u522b"
DRAFT_EDIT_READY_REQUIRED_MESSAGE = "\u53ea\u6709\u5df2\u8bc6\u522b\u5b8c\u6210\u7684 Draft \u53ef\u4ee5\u4eba\u5de5\u4fee\u6539"
DRAFT_CONTENT_EMPTY_MESSAGE = "Draft \u9898\u76ee\u6b63\u6587\u4e0d\u80fd\u4e3a\u7a7a"
QUESTION_TYPES = {"single_choice", "multiple_choice", "fill_blank", "solution", "judge", "unknown"}


class SourceAssetResponse(BaseModel):
    asset_id: int
    kind: str
    mime: str
    size_bytes: int
    width: Optional[int] = None
    height: Optional[int] = None
    sha256: str
    deduplicated: bool = False
    existing_asset_id: Optional[int] = None
    message: Optional[str] = None


def normalize_tags(raw_tags: Any) -> List[KnowledgeTag]:
    tags: List[KnowledgeTag] = []
    if not raw_tags:
        return tags
    if isinstance(raw_tags, str):
        try:
            raw_tags = json.loads(raw_tags)
        except json.JSONDecodeError:
            raw_tags = [raw_tags]
    for tag_obj in raw_tags:
        if isinstance(tag_obj, dict):
            tags.append(KnowledgeTag(label=tag_obj.get("label"), score=tag_obj.get("score", 1.0)))
        elif hasattr(tag_obj, "label"):
            tags.append(KnowledgeTag(label=getattr(tag_obj, "label"), score=getattr(tag_obj, "score", 1.0)))
        else:
            tags.append(KnowledgeTag(label=str(tag_obj), score=1.0))
    return tags


def build_question_image_url(question_id: int) -> str:
    # Authenticated image channel. Replaces the retired public /static/uploads URLs (#44).
    return f"{settings.API_V1_STR}/questions/{question_id}/image"


def _safe_remove_file(path: str) -> None:
    if not path:
        return
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError as exc:
        logger.warning("Failed to remove file {}: {}", path, exc)


def _save_upload_file(file: UploadFile, file_path: str) -> tuple[int, str]:
    sha256 = hashlib.sha256()
    size_bytes = 0
    with open(file_path, "wb") as buffer:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            size_bytes += len(chunk)
            if size_bytes > MAX_ASSET_SIZE_BYTES:
                raise HTTPException(status_code=413, detail="File too large")
            sha256.update(chunk)
            buffer.write(chunk)
    return size_bytes, sha256.hexdigest()


def _cleanup_stale_pdf_temp(pdf_temp_dir: str) -> None:
    # #103: legacy upload_pdf leaves the PDF and its page renders behind with no
    # other lifecycle; sweep files past TTL best-effort so disk usage stays bounded.
    try:
        entries = os.listdir(pdf_temp_dir)
    except OSError:
        return
    now = time.time()
    removed = 0
    for name in entries:
        path = os.path.join(pdf_temp_dir, name)
        try:
            if not os.path.isfile(path):
                continue
            if now - os.path.getmtime(path) <= PDF_TEMP_TTL_SECONDS:
                continue
            os.remove(path)
            removed += 1
        except OSError:
            continue
    if removed:
        logger.info(
            "Cleaned stale pdf_temp files dir={} count={} ttl_seconds={}",
            pdf_temp_dir,
            removed,
            PDF_TEMP_TTL_SECONDS,
        )


def _build_recognize_response(
    *,
    success: bool,
    content: str,
    knowledge: Optional[list[dict[str, Any]]] = None,
    cost_seconds: float,
    image_url: Optional[str],
    question_id: int = -1,
    created_at=None,
    error: Optional[str] = None,
    error_type: Optional[str] = None,
    partial_success: bool = False,
    warning: Optional[str] = None,
) -> OCRResponse:
    return OCRResponse(
        success=success,
        content=content,
        knowledge=knowledge or [],
        cost_seconds=round(cost_seconds, 2),
        image_url=image_url,
        id=question_id,
        created_at=created_at,
        error=error,
        error_type=error_type,
        partial_success=partial_success,
        warning=warning,
    )


def _ocr_result_to_legacy_payload(result: OCRResult | dict[str, Any]) -> dict[str, Any]:
    if isinstance(result, dict):
        return result

    payload = {
        "success": result.success,
        "content": result.text,
        "cost_seconds": round(result.latency_ms / 1000, 2),
        "provider": result.provider,
        "latency_ms": result.latency_ms,
        "raw_response_summary": result.raw_response_summary,
    }
    if not result.success:
        payload.update(
            {
                "error_type": result.error_type,
                "error": result.error,
                "detail": result.detail or result.error,
            }
        )
    return payload


def _normalize_llm_tags(raw_tags: Any) -> list[dict[str, Any]]:
    knowledge_tags: list[dict[str, Any]] = []
    if not isinstance(raw_tags, list):
        return knowledge_tags

    for tag in raw_tags:
        if isinstance(tag, str):
            label = tag.strip()
        elif isinstance(tag, dict):
            label = str(tag.get("label", "")).strip()
        else:
            label = str(tag).strip()

        if label:
            knowledge_tags.append({"label": label, "score": 1.0})
    return knowledge_tags


def _normalize_question_type(raw_question_type: Any) -> Optional[str]:
    if not isinstance(raw_question_type, str):
        return None
    question_type = raw_question_type.strip()
    if not question_type:
        return None
    return question_type if question_type in QUESTION_TYPES else "unknown"


def _extract_difficulty(llm_result: dict[str, Any]) -> dict[str, Any]:
    difficulty = llm_result.get("difficulty")
    if not isinstance(difficulty, dict):
        return {
            "difficulty_level": None,
            "difficulty_label": None,
            "difficulty_confidence": None,
            "difficulty_reason": None,
        }

    level = difficulty.get("level")
    confidence = difficulty.get("confidence")
    if not isinstance(level, int) or level < 1 or level > 5:
        return {
            "difficulty_level": None,
            "difficulty_label": None,
            "difficulty_confidence": None,
            "difficulty_reason": None,
        }
    if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
        return {
            "difficulty_level": None,
            "difficulty_label": None,
            "difficulty_confidence": None,
            "difficulty_reason": None,
        }

    return {
        "difficulty_level": level,
        "difficulty_label": difficulty.get("label"),
        "difficulty_confidence": float(confidence),
        "difficulty_reason": difficulty.get("reason"),
    }


def _apply_draft_metadata(draft: Draft, llm_result: dict[str, Any]) -> None:
    difficulty = _extract_difficulty(llm_result)
    draft.question_type = _normalize_question_type(llm_result.get("question_type"))
    draft.difficulty_level = difficulty["difficulty_level"]
    draft.difficulty_label = difficulty["difficulty_label"]
    draft.difficulty_confidence = difficulty["difficulty_confidence"]
    draft.difficulty_reason = difficulty["difficulty_reason"]


def _content_text(current_content: Any) -> str:
    if isinstance(current_content, dict):
        return str(current_content.get("text") or current_content.get("content") or "")
    if isinstance(current_content, str):
        return current_content
    return ""


def _content_tags(current_content: Any) -> list[KnowledgeTag]:
    if not isinstance(current_content, dict):
        return []
    return normalize_tags(current_content.get("knowledge_tags") or current_content.get("knowledge"))


def _extract_ocr_raw_text(draft: Draft, ocr_run: Optional[OCRRun]) -> Optional[str]:
    if isinstance(draft.current_content, dict) and isinstance(draft.current_content.get("ocr_text"), str):
        return draft.current_content["ocr_text"]
    if not ocr_run:
        return None
    if isinstance(ocr_run.parsed_blocks, list):
        block_texts = [str(block.get("text") or "") for block in ocr_run.parsed_blocks if isinstance(block, dict)]
        joined_text = "\n".join(text for text in block_texts if text).strip()
        if joined_text:
            return joined_text
    if isinstance(ocr_run.response_raw_json, dict) and isinstance(ocr_run.response_raw_json.get("content"), str):
        return ocr_run.response_raw_json["content"]
    return None


def _extract_llm_cleaned_text(draft: Draft, llm_run: Optional[LLMRun]) -> Optional[str]:
    if llm_run and isinstance(llm_run.parsed_output, dict):
        corrected_text = llm_run.parsed_output.get("corrected_text")
        if isinstance(corrected_text, str):
            return corrected_text
    if llm_run and isinstance(llm_run.raw_output, str):
        try:
            raw_output = json.loads(llm_run.raw_output)
        except json.JSONDecodeError:
            raw_output = None
        if isinstance(raw_output, dict) and isinstance(raw_output.get("corrected_text"), str):
            return raw_output["corrected_text"]
    if llm_run:
        return _content_text(draft.current_content) or None
    return None


def _run_error(error_code: Optional[str], error_message: Optional[str]) -> Optional[str]:
    if error_code and error_message:
        return f"{error_code}: {error_message}"
    return error_message or error_code


def _build_recognition_debug(draft: Draft) -> Optional[RecognitionDebug]:
    ocr_run = draft.last_ocr_run
    llm_run = draft.last_llm_run
    if not ocr_run and not llm_run:
        return None
    return RecognitionDebug(
        ocr_provider=ocr_run.provider if ocr_run else None,
        ocr_raw_text=_extract_ocr_raw_text(draft, ocr_run),
        llm_cleaned_text=_extract_llm_cleaned_text(draft, llm_run),
        ocr_error=_run_error(ocr_run.error_code, ocr_run.error_message) if ocr_run else None,
        llm_error=_run_error(llm_run.error_code, llm_run.error_message) if llm_run else None,
    )


def _build_draft_detail(draft: Draft) -> DraftDetail:
    recognition_debug = _build_recognition_debug(draft)
    content_text = _content_text(draft.current_content)
    has_recognition_text = bool(
        content_text.strip()
        or (recognition_debug and (recognition_debug.ocr_raw_text or recognition_debug.llm_cleaned_text))
    )
    return DraftDetail(
        id=draft.id,
        source_asset_id=draft.source_asset_id,
        crop_bbox=draft.crop_bbox,
        detected_figures=[
            FigureDetection(**figure) for figure in (draft.detected_figures or [])
        ],
        status=draft.status,
        current_content=draft.current_content,
        content=content_text,
        knowledge_tags=_content_tags(draft.current_content),
        question_type=draft.question_type,
        difficulty_level=draft.difficulty_level,
        difficulty_label=draft.difficulty_label,
        difficulty_confidence=draft.difficulty_confidence,
        difficulty_reason=draft.difficulty_reason,
        last_ocr_run_id=draft.last_ocr_run_id,
        last_llm_run_id=draft.last_llm_run_id,
        recognition_debug=recognition_debug,
        quality_warnings=detect_quality_warnings(
            content_text,
            raw_ocr_text=recognition_debug.ocr_raw_text if recognition_debug else None,
            llm_cleaned_text=recognition_debug.llm_cleaned_text if recognition_debug else None,
            question_type=draft.question_type,
        )
        if has_recognition_text
        else [],
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


def _asset_file_path(asset: SourceAsset) -> str:
    stored_path = asset.normalized_path or asset.original_path
    if os.path.isabs(stored_path):
        return stored_path
    return str(settings.UPLOAD_DIR_PATH / stored_path)


def _ensure_owned_asset(db: Session, asset_id: int, user_id: int) -> SourceAsset:
    asset = db.query(SourceAsset).filter(SourceAsset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)
    if asset.user_id != user_id:
        raise HTTPException(status_code=403, detail=FORBIDDEN_MESSAGE)
    return asset


def _ensure_owned_draft(db: Session, draft_id: int, user_id: int) -> Draft:
    draft = db.query(Draft).filter(Draft.id == draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)
    if draft.user_id != user_id:
        raise HTTPException(status_code=403, detail=FORBIDDEN_MESSAGE)
    return draft


@router.get("/tags", response_model=List[str])
def get_all_tags(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    questions = db.query(Question).filter(
        Question.user_id == current_user.id,
        Question.deleted_at.is_(None),
        Question.purged_at.is_(None),
    ).all()

    unique_tags = set()
    for question in questions:
        for tag_obj in normalize_tags(question.knowledge_tags):
            unique_tags.add(tag_obj.label)

    return sorted(list(unique_tags))


@router.put("/questions/{question_id}")
def update_question(
    question_id: int,
    question_update: QuestionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    question, created, revision = update_question_service(db, current_user, question_id, question_update)
    return {
        "success": True,
        "msg": QUESTION_UPDATED_MESSAGE,
        "revision_created": created,
        "current_revision_no": revision.rev_no if revision else None,
        "question": question,
    }


@router.get("/history", response_model=List[OCRResponse])
def read_history(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    questions = (
        db.query(Question)
        .filter(
            Question.user_id == current_user.id,
            Question.deleted_at.is_(None),
            Question.purged_at.is_(None),
        )
        .order_by(Question.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    logger.info("Reading history records user_id={} rows={}", current_user.id, len(questions))
    results = []
    for question in questions:
        results.append(
            OCRResponse(
                success=True,
                content=question.content or "",
                knowledge=normalize_tags(question.knowledge_tags),
                cost_seconds=0.0,
                image_url=build_question_image_url(question.id),
                id=question.id,
                created_at=question.created_at,
            )
        )
    return results


@router.post("/upload_pdf")
def upload_pdf(
    file: UploadFile = File(...),
    current_user: User = Depends(require_active_user),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail=PDF_ONLY_MESSAGE)

    pdf_temp_dir = str(settings.PDF_TEMP_DIR_PATH)
    os.makedirs(pdf_temp_dir, exist_ok=True)

    file_ext = file.filename.split(".")[-1]
    task_id = str(uuid.uuid4())
    pdf_filename = f"{task_id}.{file_ext}"
    pdf_path = os.path.join(pdf_temp_dir, pdf_filename)

    _cleanup_stale_pdf_temp(pdf_temp_dir)

    # #103: bounded copy aligned with /assets — no unbounded disk writes.
    try:
        _save_upload_file(file, pdf_path)
    except HTTPException:
        _safe_remove_file(pdf_path)
        raise
    except Exception:
        logger.exception("Failed to save pdf upload user_id={} path={}", current_user.id, pdf_path)
        _safe_remove_file(pdf_path)
        raise HTTPException(status_code=500, detail=UPLOAD_SAVE_FAILED_MESSAGE)
    finally:
        try:
            file.file.close()
        except Exception:
            pass

    image_list = []
    try:
        document = fitz.open(pdf_path)
        if len(document) > MAX_PDF_PAGES:
            document.close()
            _safe_remove_file(pdf_path)
            logger.warning(
                "PDF page limit exceeded user_id={} limit={}",
                current_user.id,
                MAX_PDF_PAGES,
            )
            raise HTTPException(status_code=413, detail=PDF_TOO_MANY_PAGES_MESSAGE)
        for page_index in range(len(document)):
            page = document.load_page(page_index)
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
            img_name = f"{task_id}_page_{page_index}.jpg"
            img_path = os.path.join(pdf_temp_dir, img_name)
            pix.save(img_path)
            image_list.append(f"pdf_temp/{img_name}")
        document.close()
        return {"success": True, "total_pages": len(image_list), "images": image_list}
    except HTTPException:
        _safe_remove_file(pdf_path)
        raise
    except Exception:
        logger.exception("PDF parse failed user_id={} path={}", current_user.id, pdf_path)
        _safe_remove_file(pdf_path)
        raise HTTPException(status_code=500, detail=PDF_PARSE_FAILED_MESSAGE)
    finally:
        try:
            file.file.close()
        except Exception:
            pass


@router.post("/assets", response_model=SourceAssetResponse)
def upload_asset(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    mime = file.content_type or mimetypes.guess_type(file.filename)[0] or ""
    if mime not in ALLOWED_ASSET_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    original_name = os.path.basename(file.filename)
    if not original_name:
        raise HTTPException(status_code=400, detail="Invalid filename")

    unique_prefix = uuid.uuid4().hex
    stored_filename = f"{unique_prefix}_{original_name}"
    file_path = str(settings.UPLOAD_DIR_PATH / stored_filename)

    try:
        size_bytes, sha256_digest = _save_upload_file(file, file_path)
    except HTTPException:
        _safe_remove_file(file_path)
        raise
    finally:
        try:
            file.file.close()
        except Exception:
            pass

    width = None
    height = None
    kind = "pdf"
    if mime.startswith("image/"):
        kind = "image"
        try:
            with Image.open(file_path) as img:
                width, height = img.size
        except Exception:
            _safe_remove_file(file_path)
            raise HTTPException(status_code=400, detail="Invalid image file")

    asset = SourceAsset(
        user_id=current_user.id,
        kind=kind,
        original_path=stored_filename,
        normalized_path=None,
        mime=mime,
        size_bytes=size_bytes,
        width=width,
        height=height,
        sha256=sha256_digest,
    )

    db.add(asset)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        _safe_remove_file(file_path)
        existing_asset = (
            db.query(SourceAsset)
            .filter(SourceAsset.user_id == current_user.id, SourceAsset.sha256 == sha256_digest)
            .first()
        )
        if not existing_asset:
            raise HTTPException(status_code=409, detail="Asset already exists")
        return SourceAssetResponse(
            asset_id=existing_asset.id,
            kind=existing_asset.kind,
            mime=existing_asset.mime,
            size_bytes=existing_asset.size_bytes,
            width=existing_asset.width,
            height=existing_asset.height,
            sha256=existing_asset.sha256,
            deduplicated=True,
            existing_asset_id=existing_asset.id,
            message="Asset already exists, using existing asset.",
        )
    db.refresh(asset)

    return SourceAssetResponse(
        asset_id=asset.id,
        kind=asset.kind,
        mime=asset.mime,
        size_bytes=asset.size_bytes,
        width=asset.width,
        height=asset.height,
        sha256=asset.sha256,
    )


@router.post("/drafts", response_model=DraftDetail)
def create_draft(
    payload: DraftCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    _ensure_owned_asset(db, payload.source_asset_id, current_user.id)

    draft = Draft(
        user_id=current_user.id,
        source_asset_id=payload.source_asset_id,
        crop_bbox=payload.crop_bbox,
        status=DraftStatus.DRAFT_CREATED,
        current_content={"text": "", "knowledge_tags": []},
    )
    db.add(draft)
    db.flush()
    db.add(
        DraftEvent(
            draft_id=draft.id,
            from_status=None,
            to_status=DraftStatus.DRAFT_CREATED,
            event_type=DraftEventType.CREATE,
            metadata_={"source_asset_id": payload.source_asset_id},
        )
    )
    db.commit()
    db.refresh(draft)

    return _build_draft_detail(draft)


@router.get("/drafts/{draft_id}", response_model=DraftDetail)
def get_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    draft = _ensure_owned_draft(db, draft_id, current_user.id)
    return _build_draft_detail(draft)


@router.get("/drafts/{draft_id}/image")
def get_draft_image(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    # Issue #22: serve the SourceAsset image behind a Draft so the editor can
    # reference the recognized region next to the recognition result.
    # Ownership is enforced on the Draft row on purpose (same rationale as
    # get_question_image): SourceAsset rows are deduplicated by sha256 across
    # users, so the asset row itself carries no owner semantics.
    draft = _ensure_owned_draft(db, draft_id, current_user.id)
    asset = draft.source_asset or (
        db.query(SourceAsset).filter(SourceAsset.id == draft.source_asset_id).first()
    )
    if not asset:
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)

    file_path = resolve_upload_file_path(asset.normalized_path or asset.original_path)
    if not file_path:
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)

    if not draft.crop_bbox:
        return FileResponse(file_path, media_type=asset.mime)
    try:
        content, media_type = render_draft_image(file_path, draft.crop_bbox)
    except Exception:
        logger.exception("Failed to render cropped Draft image draft_id={}", draft.id)
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.patch("/drafts/{draft_id}", response_model=DraftDetail)
def update_draft(
    draft_id: int,
    payload: DraftUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    draft = _ensure_owned_draft(db, draft_id, current_user.id)
    if draft.status != DraftStatus.DRAFT_READY:
        raise HTTPException(status_code=409, detail=DRAFT_EDIT_READY_REQUIRED_MESSAGE)

    normalized_content = payload.content.strip()
    if not normalized_content:
        raise HTTPException(status_code=422, detail=DRAFT_CONTENT_EMPTY_MESSAGE)

    previous_content = _content_text(draft.current_content)
    if normalized_content == previous_content:
        return _build_draft_detail(draft)

    current_content = dict(draft.current_content or {})
    current_content["text"] = normalized_content
    draft.current_content = current_content
    db.add(
        DraftEvent(
            draft_id=draft.id,
            from_status=DraftStatus.DRAFT_READY,
            to_status=DraftStatus.DRAFT_READY,
            event_type=DraftEventType.EDIT,
            metadata_={
                "source": "manual_review",
                "previous_length": len(previous_content),
                "new_length": len(normalized_content),
                "previous_sha256": hashlib.sha256(previous_content.encode("utf-8")).hexdigest(),
                "new_sha256": hashlib.sha256(normalized_content.encode("utf-8")).hexdigest(),
            },
        )
    )
    db.commit()
    db.refresh(draft)
    return _build_draft_detail(draft)


@router.post("/drafts/{draft_id}/recognize", response_model=DraftRecognizeResponse)
def recognize_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    total_started_at = time.time()
    draft = _ensure_owned_draft(db, draft_id, current_user.id)
    if draft.status == DraftStatus.SAVED_TO_BANK:
        raise HTTPException(status_code=409, detail=DRAFT_ALREADY_SAVED_RECOGNIZE_MESSAGE)
    if draft.status == DraftStatus.RECOGNIZING:
        raise HTTPException(status_code=409, detail="Draft 正在识别中，请勿重复提交")

    asset = _ensure_owned_asset(db, draft.source_asset_id, current_user.id)
    if not asset.mime.startswith("image/"):
        raise HTTPException(status_code=400, detail="Draft recognition currently supports image assets only")

    transition_draft_status(
        db,
        draft,
        DraftStatus.RECOGNIZING,
        DraftEventType.START_RECOGNIZE,
        metadata={"source_asset_id": asset.id},
        commit=True,
    )

    file_path = _asset_file_path(asset)
    cropped_temp_path = None
    try:
        cropped_temp_path = create_cropped_temp_image(file_path, draft.crop_bbox)
    except Exception:
        logger.exception("Failed to crop Draft image draft_id={} bbox={}", draft.id, draft.crop_bbox)
        transition_draft_status(
            db,
            draft,
            DraftStatus.FAILED,
            DraftEventType.RECOGNIZE_FAIL,
            metadata={"failure_stage": "crop"},
            commit=True,
        )
        raise HTTPException(status_code=400, detail="Draft 裁剪区域无法处理")
    recognition_image_path = str(cropped_temp_path) if cropped_temp_path is not None else file_path

    # #58: detect figure regions before OCR so figure areas can be masked out
    # of the OCR input. Any detection problem degrades to the pre-#58 flow
    # (no figures recorded, original image sent to OCR).
    layout_started_at = time.time()
    try:
        layout_result = layout_service.detect(recognition_image_path)
    except Exception:
        logger.exception("Unexpected layout crash draft_id={} user_id={}", draft.id, current_user.id)
        layout_result = None
    layout_ms = int((time.time() - layout_started_at) * 1000)

    detected_figures: list[dict[str, Any]] = []
    masked_temp_path = None
    if layout_result is not None and layout_result.success and layout_result.boxes:
        detected_figures = [
            {"bbox": box.bbox, "label": box.label, "score": box.score}
            for box in layout_result.boxes
        ]
        try:
            masked_temp_path = write_masked_image(recognition_image_path, layout_result.boxes)
        except Exception:
            # Masking failure degrades to unmasked OCR instead of leaking the
            # question crop temp file (it is always removed in the OCR finally).
            logger.exception("Unexpected figure masking crash draft_id={} user_id={}", draft.id, current_user.id)
            masked_temp_path = None
    elif layout_result is not None and not layout_result.success:
        logger.warning(
            "[LayoutDetect] degraded draft_id={} error_type={} detail={} latency_ms={}",
            draft.id,
            layout_result.error_type,
            layout_result.detail,
            layout_result.latency_ms,
        )
    draft.detected_figures = detected_figures

    if masked_temp_path is not None:
        ocr_input_mode = "masked_with_figures"
    elif cropped_temp_path is not None:
        ocr_input_mode = "cropped"
    else:
        ocr_input_mode = "original"
    ocr_input_path = str(masked_temp_path) if masked_temp_path is not None else recognition_image_path
    ocr_started_at = time.time()
    try:
        ocr_result = _ocr_result_to_legacy_payload(draft_ocr_service.recognize(ocr_input_path))
    except Exception:
        logger.exception("Unexpected Draft OCR crash draft_id={} user_id={}", draft.id, current_user.id)
        ocr_result = {
            "success": False,
            "content": "",
            "cost_seconds": 0.0,
            "provider": getattr(draft_ocr_service, "provider_name", "unknown"),
            "error_type": "service_error",
            "error": "\u6587\u5b57\u8bc6\u522b\u670d\u52a1\u8c03\u7528\u5931\u8d25",
            "detail": "ocr_unexpected_error",
        }
    finally:
        remove_quiet(masked_temp_path)
        remove_quiet(cropped_temp_path)
    ocr_ms = int((time.time() - ocr_started_at) * 1000)

    raw_content = (ocr_result.get("content") or "").strip()
    ocr_provider = ocr_result.get("provider") or getattr(draft_ocr_service, "provider_name", "unknown")
    ocr_latency_ms = int(ocr_result.get("latency_ms") or int(float(ocr_result.get("cost_seconds") or 0) * 1000))
    ocr_run = OCRRun(
        draft_id=draft.id,
        provider=ocr_provider,
        endpoint=getattr(draft_ocr_service, "endpoint", None),
        request_params_redacted={
            "source_asset_id": asset.id,
            "crop_bbox": draft.crop_bbox,
            "ocr_input": ocr_input_mode,
        },
        response_raw_json=ocr_result,
        parsed_blocks=[{"text": raw_content}] if raw_content else [],
        latency_ms=ocr_latency_ms,
        error_code=None if ocr_result.get("success") else ocr_result.get("error_type"),
        error_message=None if ocr_result.get("success") else (ocr_result.get("detail") or ocr_result.get("error")),
        text_len_estimate=len(raw_content),
    )
    db.add(ocr_run)
    db.flush()
    draft.last_ocr_run_id = ocr_run.id

    if not ocr_result.get("success"):
        draft.current_content = {
            "text": "",
            "ocr_text": raw_content,
            "knowledge_tags": [],
            "error": ocr_result.get("error"),
            "error_type": ocr_result.get("error_type"),
        }
        transition_draft_status(
            db,
            draft,
            DraftStatus.FAILED,
            DraftEventType.RECOGNIZE_FAIL,
            metadata={"ocr_run_id": ocr_run.id, "error_type": ocr_result.get("error_type")},
            commit=True,
        )
        logger.info(
            "[DraftRecognizePerf] draft_id={} asset_id={} ocr_provider={} ocr_ms={} llm_text_ms={} total_ms={} model={} ocr_text_len={} corrected_text_len={} llm_fallback={} fallback_reason={} failure_stage={} layout_ms={} layout_boxes={}",
            draft.id,
            asset.id,
            ocr_provider,
            ocr_ms,
            0,
            int((time.time() - total_started_at) * 1000),
            settings.DEEPSEEK_MODEL,
            len(raw_content),
            0,
            True,
            ocr_result.get("error_type"),
            "ocr",
            layout_ms,
            len(detected_figures),
        )
        detail = _build_draft_detail(draft)
        return DraftRecognizeResponse(
            **detail.model_dump(),
            success=False,
            error=ocr_result.get("error"),
            error_type=ocr_result.get("error_type"),
        )

    final_content = raw_content
    knowledge_tags: list[dict[str, Any]] = []
    warning = None
    partial_success = False

    llm_started_at = time.time()
    try:
        llm_result = nlp_service.analyze(raw_content)
    except Exception:
        logger.exception("Unexpected Draft LLM crash draft_id={} user_id={}", draft.id, current_user.id)
        llm_result = {
            "success": False,
            "error_type": "service_error",
            "error": "\u667a\u80fd\u6574\u7406\u670d\u52a1\u8c03\u7528\u5931\u8d25",
            "detail": "llm_unexpected_error",
            "corrected_text": raw_content,
            "tags": [],
            "cost_seconds": 0.0,
        }
    llm_text_ms = int((time.time() - llm_started_at) * 1000)

    if llm_result.get("success"):
        final_content = llm_result.get("corrected_text", raw_content) or raw_content
        knowledge_tags = _normalize_llm_tags(llm_result.get("knowledge_tags", llm_result.get("tags", [])))
        _apply_draft_metadata(draft, {})
    else:
        partial_success = True
        warning = llm_result.get("error") or "\u667a\u80fd\u6574\u7406\u5931\u8d25\uff0c\u5df2\u4fdd\u7559\u539f\u59cb\u8bc6\u522b\u7ed3\u679c"
        final_content = llm_result.get("corrected_text", raw_content) or raw_content
        knowledge_tags = _normalize_llm_tags(llm_result.get("knowledge_tags", llm_result.get("tags", [])))
        _apply_draft_metadata(draft, {})

    llm_run = LLMRun(
        draft_id=draft.id,
        provider="deepseek",
        model=settings.DEEPSEEK_MODEL,
        prompt_version="v1",
        input_text=raw_content,
        raw_output=json.dumps(llm_result, ensure_ascii=False),
        parsed_output=llm_result,
        json_valid=bool(llm_result.get("success")),
        schema_valid=bool(llm_result.get("success")),
        fallback_used=partial_success,
        latency_ms=int(float(llm_result.get("cost_seconds") or 0) * 1000),
        error_code=None if llm_result.get("success") else llm_result.get("error_type"),
        error_message=None if llm_result.get("success") else (llm_result.get("detail") or llm_result.get("error")),
    )
    db.add(llm_run)
    db.flush()

    draft.last_llm_run_id = llm_run.id
    draft.current_content = {
        "text": final_content,
        "ocr_text": raw_content,
        "knowledge_tags": knowledge_tags,
        "partial_success": partial_success,
        "warning": warning,
    }
    transition_draft_status(
        db,
        draft,
        DraftStatus.DRAFT_READY,
        DraftEventType.RECOGNIZE_SUCCESS,
        metadata={
            "ocr_run_id": ocr_run.id,
            "llm_run_id": llm_run.id,
            "partial_success": partial_success,
            "metadata_warning": llm_result.get("metadata_warning"),
        },
        commit=True,
    )

    logger.info(
        "[DraftRecognizePerf] draft_id={} asset_id={} ocr_provider={} ocr_ms={} llm_text_ms={} total_ms={} model={} ocr_text_len={} corrected_text_len={} llm_fallback={} fallback_reason={} failure_stage={} layout_ms={} layout_boxes={}",
        draft.id,
        asset.id,
        ocr_provider,
        ocr_ms,
        llm_text_ms,
        int((time.time() - total_started_at) * 1000),
        settings.DEEPSEEK_MODEL,
        len(raw_content),
        len(final_content or ""),
        partial_success,
        llm_result.get("error_type") if partial_success else None,
        "llm" if partial_success else None,
        layout_ms,
        len(detected_figures),
    )

    detail = _build_draft_detail(draft)
    return DraftRecognizeResponse(
        **detail.model_dump(),
        success=True,
        partial_success=partial_success,
        warning=warning,
        error_type="llm_failed" if partial_success else None,
    )


def _valid_figure_bbox(figure_bbox: Any) -> Optional[list[float]]:
    """Validate a user-confirmed figure bbox: [x, y, w, h] normalized to [0, 1]."""
    try:
        values = [float(v) for v in figure_bbox]
    except (TypeError, ValueError):
        return None
    if len(values) != 4:
        return None
    x, y, w, h = values
    if not all(0.0 <= value <= 1.0 for value in (x, y, w, h)):
        return None
    if w <= 0 or h <= 0 or (w * h) < float(settings.LAYOUT_MIN_AREA_RATIO):
        return None
    return [x, y, w, h]


def _attach_question_figure(
    db: Session,
    question: Question,
    revision: QuestionRevision,
    asset: SourceAsset,
    figure_bbox: Any,
    draft_id: int,
    crop_bbox: Any = None,
) -> None:
    """Crop the confirmed figure region out of the original page asset (#58).

    figure_bbox is normalized relative to the Draft's effective question image
    (which is the whole page for legacy/full-image Drafts). It is validated
    against LAYOUT_MIN_AREA_RATIO in that same crop-relative space — matching
    how the layout detector reports figures — then composed into page
    coordinates before cropping from the full-resolution source, so small
    figures in small question crops are not silently dropped.

    Best-effort: any failure logs and leaves the question without a figure
    instead of blocking save-to-bank.
    """
    normalized = _valid_figure_bbox(figure_bbox)
    if normalized is None:
        logger.warning("[FigureCrop] ignored invalid figure_bbox draft_id={} bbox={}", draft_id, figure_bbox)
        return
    page_bbox = compose_bbox_to_page(crop_bbox, normalized)
    if page_bbox is None:
        logger.warning("[FigureCrop] ignored uncomposable figure_bbox draft_id={} bbox={}", draft_id, figure_bbox)
        return
    try:
        source_path = _asset_file_path(asset)
        with Image.open(source_path) as img:
            rgb = img.convert("RGB")
            x, y, w, h = page_bbox
            left = min(max(round(x * rgb.width), 0), rgb.width - 1)
            top = min(max(round(y * rgb.height), 0), rgb.height - 1)
            right = min(max(round((x + w) * rgb.width), left + 1), rgb.width)
            bottom = min(max(round((y + h) * rgb.height), top + 1), rgb.height)
            crop = rgb.crop((left, top, right, bottom))
            crop.load()

        filename = f"{uuid.uuid4().hex}_figure.jpg"
        out_path = settings.UPLOAD_DIR_PATH / filename
        out_path.parent.mkdir(parents=True, exist_ok=True)
        crop.save(out_path, format="JPEG", quality=90)
        data = out_path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()

        existing = db.query(SourceAsset).filter(SourceAsset.sha256 == digest).first()
        if existing is not None:
            # Same crop bytes already stored (sha256 dedup): drop our duplicate file.
            out_path.unlink(missing_ok=True)
            figure_asset = existing
        else:
            figure_asset = SourceAsset(
                user_id=question.user_id,
                kind="figure",
                original_path=filename,
                mime="image/jpeg",
                size_bytes=len(data),
                width=crop.width,
                height=crop.height,
                sha256=digest,
            )
            db.add(figure_asset)
            db.flush()

        question.figure_image = figure_asset.normalized_path or figure_asset.original_path
        question.figure_crop_bbox = page_bbox
        revision.figure_asset_id = figure_asset.id
        logger.info(
            "[FigureCrop] attached figure asset_id={} question_id={} bbox={}",
            figure_asset.id,
            question.id,
            page_bbox,
        )
    except Exception:
        logger.exception("Figure crop failed; saving question without figure question_id={}", question.id)


@router.post("/drafts/{draft_id}/save-to-bank", response_model=DraftSaveToBankResponse)
def save_draft_to_bank(
    draft_id: int,
    background_tasks: BackgroundTasks,
    payload: Optional[DraftSaveToBankRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    draft = _ensure_owned_draft(db, draft_id, current_user.id)
    if draft.status == DraftStatus.SAVED_TO_BANK:
        raise HTTPException(status_code=409, detail=DRAFT_ALREADY_SAVED_MESSAGE)

    if draft.status != DraftStatus.DRAFT_READY:
        raise HTTPException(status_code=409, detail=DRAFT_READY_REQUIRED_MESSAGE)

    content_text = _content_text(draft.current_content).strip()
    knowledge_tags = [tag.model_dump() for tag in _content_tags(draft.current_content)]

    question = Question(
        user_id=current_user.id,
        content=content_text,
        knowledge_tags=knowledge_tags,
        metadata_status="pending",
        origin_image=(draft.source_asset.normalized_path or draft.source_asset.original_path)
        if draft.source_asset
        else None,
    )
    db.add(question)
    db.flush()

    revision = QuestionRevision(
        question_id=question.id,
        rev_no=1,
        content=draft.current_content or {"text": content_text, "knowledge_tags": knowledge_tags},
        crop_bbox=draft.crop_bbox,
        source_asset_id=draft.source_asset_id,
        ocr_run_id=draft.last_ocr_run_id,
        llm_run_id=draft.last_llm_run_id,
        change_reason="draft_save_to_bank",
    )
    db.add(revision)
    db.flush()

    figure_bbox = payload.figure_bbox if payload else None
    if figure_bbox is not None and draft.source_asset is not None:
        _attach_question_figure(
            db,
            question,
            revision,
            draft.source_asset,
            figure_bbox,
            draft_id=draft.id,
            crop_bbox=draft.crop_bbox,
        )

    transition_draft_status(
        db,
        draft,
        DraftStatus.SAVED_TO_BANK,
        DraftEventType.SAVE_TO_BANK,
        metadata={"question_id": question.id, "question_revision_id": revision.id, "rev_no": revision.rev_no},
        commit=True,
    )
    db.refresh(question)
    db.refresh(revision)
    db.refresh(draft)
    background_tasks.add_task(evaluate_question_metadata_task, question.id)

    detail = _build_draft_detail(draft)
    return DraftSaveToBankResponse(
        **detail.model_dump(),
        question_id=question.id,
        question_revision_id=revision.id,
        rev_no=revision.rev_no,
    )


@router.post("/papers", response_model=PaperRead)
def create_paper_endpoint(
    payload: PaperCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    return create_paper(db, current_user, payload)


@router.get("/papers", response_model=List[PaperListItem])
def list_papers_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    return list_papers(db, current_user)


@router.get("/papers/{paper_id}", response_model=PaperRead)
def get_paper_endpoint(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    return get_paper(db, current_user, paper_id)


@router.patch("/papers/{paper_id}", response_model=PaperRead)
def update_paper_endpoint(
    paper_id: int,
    payload: PaperUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    return update_paper(db, current_user, paper_id, payload)


@router.post("/papers/{paper_id}/render-model", response_model=PaperRenderModel)
def get_paper_render_model_endpoint(
    paper_id: int,
    payload: PaperRenderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    return build_paper_render_model(db, current_user, paper_id, payload)


def _paper_pdf_content_disposition(title: str, paper_id: int) -> str:
    normalized = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", title, flags=re.UNICODE).strip("._")
    unicode_filename = f"{(normalized[:64] or f'paper-{paper_id}')}.pdf"
    return (
        f'attachment; filename="paper-{paper_id}.pdf"; '
        f"filename*=UTF-8''{quote(unicode_filename, safe='')}"
    )


@router.post("/papers/{paper_id}/pdf")
def generate_paper_pdf_endpoint(
    paper_id: int,
    payload: PaperRenderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    render_model = build_paper_render_model(db, current_user, paper_id, payload)
    options = PdfGenerationOptions.a4_portrait()

    figure_files = resolve_paper_figure_files(db, current_user, paper_id)

    def figure_loader(item: PaperRenderItem) -> Optional[tuple[bytes, Optional[str]]]:
        path = figure_files.get(item.paper_item_id)
        if not path:
            return None
        try:
            return Path(path).read_bytes(), mimetypes.guess_type(path)[0]
        except OSError:
            logger.warning(
                "Paper figure unreadable paper_id={} paper_item_id={} path={}",
                paper_id,
                item.paper_item_id,
                path,
            )
            return None

    try:
        printable_html = render_paper_html(render_model, options, figure_loader=figure_loader)
        pdf_bytes = pdf_generation_service.generate_pdf(printable_html, options)
    except PaperFigureTooLargeError as exc:
        # The renderer's message names the offending question; pass it through (#59).
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except PaperHtmlRenderError as exc:
        raise HTTPException(status_code=413, detail=PDF_PAPER_TOO_LARGE_MESSAGE) from exc
    except PdfGenerationError as exc:
        logger.exception(
            "Paper PDF generation failed paper_id={} user_id={}",
            paper_id,
            current_user.id,
        )
        raise HTTPException(status_code=503, detail=PDF_GENERATION_UNAVAILABLE_MESSAGE) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": _paper_pdf_content_disposition(render_model.paper.title, paper_id),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/papers/{paper_id}/items/{paper_item_id}/image")
def get_paper_item_figure(
    paper_id: int,
    paper_item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    # Papers-domain ownership convention (#59): a missing paper, a foreign
    # paper, an item belonging to another paper, and a missing/unresolvable
    # snapshot all answer 404 — deliberately unlike the questions-image 404/403
    # split, mirroring the get/render/pdf paper routes.
    paper = db.query(Paper).filter(Paper.id == paper_id, Paper.user_id == current_user.id).first()
    if not paper:
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)
    paper_item = next((item for item in (paper.items or []) if item.id == paper_item_id), None)
    if paper_item is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)

    # Serve the filename frozen at creation time so later re-crops or edits of
    # the source question never alter historical papers (snapshot semantics).
    file_path = resolve_upload_file_path(paper_item.figure_image_snapshot)
    if not file_path:
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)

    return FileResponse(file_path)


# Legacy compatibility endpoint. Keep behavior unchanged while Dashboard uses the Draft flow.
@router.post("/recognize", response_model=OCRResponse)
def recognize_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    start_total = time.time()

    file_ext = os.path.splitext(file.filename or "")[1].lower()
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = str(settings.UPLOAD_DIR_PATH / unique_filename)

    logger.info("Saving recognize upload user_id={} path={}", current_user.id, file_path)
    # #103: bounded copy aligned with /assets — no unbounded disk writes.
    try:
        _save_upload_file(file, file_path)
    except HTTPException:
        _safe_remove_file(file_path)
        raise
    except Exception:
        logger.exception("Failed to save recognize upload path={}", file_path)
        _safe_remove_file(file_path)
        raise HTTPException(status_code=500, detail=UPLOAD_SAVE_FAILED_MESSAGE)
    finally:
        try:
            file.file.close()
        except Exception:
            pass

    try:
        ocr_result = ocr_service.recognize(file_path)
    except Exception:
        logger.exception("Unexpected OCR crash user_id={} path={}", current_user.id, file_path)
        _safe_remove_file(file_path)
        return _build_recognize_response(
            success=False,
            content="",
            cost_seconds=time.time() - start_total,
            image_url=None,
            error="\u6587\u5b57\u8bc6\u522b\u670d\u52a1\u8c03\u7528\u5931\u8d25",
            error_type="service_error",
        )

    raw_content = (ocr_result.get("content") or "").strip()
    if not ocr_result.get("success"):
        logger.warning(
            "Recognize OCR failed user_id={} type={} detail={}",
            current_user.id,
            ocr_result.get("error_type"),
            ocr_result.get("detail"),
        )
        _safe_remove_file(file_path)
        return _build_recognize_response(
            success=False,
            content="",
            cost_seconds=time.time() - start_total,
            image_url=None,
            error=ocr_result.get("error"),
            error_type=ocr_result.get("error_type"),
        )

    logger.info(
        "Recognize OCR succeeded user_id={} chars={} cost_seconds={}",
        current_user.id,
        len(raw_content),
        ocr_result.get("cost_seconds"),
    )
    logger.debug("OCR raw content: {}", raw_content)

    final_content = raw_content
    knowledge_tags: list[dict[str, Any]] = []
    warning = None
    partial_success = False

    if raw_content:
        try:
            logger.info("Running LLM post-processing user_id={}", current_user.id)
            llm_result = nlp_service.analyze(raw_content)
        except Exception:
            logger.exception("Unexpected LLM crash user_id={}", current_user.id)
            llm_result = {
                "success": False,
                "error_type": "service_error",
                "error": "\u667a\u80fd\u6574\u7406\u670d\u52a1\u8c03\u7528\u5931\u8d25",
                "detail": "llm_unexpected_error",
                "corrected_text": raw_content,
                "tags": [],
            }

        if llm_result.get("success"):
            final_content = llm_result.get("corrected_text", raw_content) or raw_content
            knowledge_tags = _normalize_llm_tags(llm_result.get("knowledge_tags", llm_result.get("tags", [])))
        else:
            partial_success = True
            warning = llm_result.get("error") or "\u667a\u80fd\u6574\u7406\u5931\u8d25\uff0c\u5df2\u4fdd\u7559\u539f\u59cb\u8bc6\u522b\u7ed3\u679c"
            logger.warning(
                "Recognize LLM failed user_id={} type={} detail={}",
                current_user.id,
                llm_result.get("error_type"),
                llm_result.get("detail"),
            )
            final_content = llm_result.get("corrected_text", raw_content) or raw_content
            knowledge_tags = _normalize_llm_tags(llm_result.get("knowledge_tags", llm_result.get("tags", [])))

    try:
        new_question = Question(
            origin_image=unique_filename,
            user_id=current_user.id,
            content=final_content,
            knowledge_tags=knowledge_tags,
            question_type=_normalize_question_type(llm_result.get("question_type")) if raw_content else None,
            difficulty_level=_extract_difficulty(llm_result)["difficulty_level"] if raw_content else None,
            difficulty_label=_extract_difficulty(llm_result)["difficulty_label"] if raw_content else None,
            difficulty_confidence=_extract_difficulty(llm_result)["difficulty_confidence"] if raw_content else None,
            difficulty_reason=_extract_difficulty(llm_result)["difficulty_reason"] if raw_content else None,
            difficulty_model=settings.DEEPSEEK_MODEL
            if raw_content and _extract_difficulty(llm_result)["difficulty_level"] is not None
            else None,
            difficulty_evaluated_at=datetime.now(timezone.utc)
            if raw_content and _extract_difficulty(llm_result)["difficulty_level"] is not None
            else None,
        )
        db.add(new_question)
        db.commit()
        db.refresh(new_question)
        logger.info(
            "Question persisted id={} user_id={} partial_success={}",
            new_question.id,
            current_user.id,
            partial_success,
        )
    except Exception:
        logger.exception("Database error while creating question user_id={}", current_user.id)
        db.rollback()
        _safe_remove_file(file_path)
        raise HTTPException(status_code=500, detail=QUESTION_SAVE_FAILED_MESSAGE)

    return _build_recognize_response(
        success=True,
        content=final_content,
        knowledge=knowledge_tags,
        cost_seconds=time.time() - start_total,
        image_url=build_question_image_url(new_question.id),
        question_id=new_question.id,
        created_at=new_question.created_at,
        partial_success=partial_success,
        warning=warning,
        error_type="llm_failed" if partial_success else None,
    )


@router.get("/questions", response_model=List[QuestionListItem])
def list_questions(
    skip: int = 0,
    limit: int = 50,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    query = db.query(Question).filter(Question.user_id == current_user.id, Question.deleted_at.is_(None), Question.purged_at.is_(None))
    if q:
        query = query.filter(Question.content.contains(q))

    questions = (
        query.order_by(Question.created_at.desc(), Question.id.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return [
        QuestionListItem(
            id=item.id,
            content=item.content,
            answer=item.answer,
            analysis=item.analysis,
            current_revision_no=(latest_question_revision(db, item.id).rev_no if latest_question_revision(db, item.id) else None),
            deleted_at=item.deleted_at,
            purge_at=item.purge_at,
            purged_at=item.purged_at,
            knowledge_tags=normalize_tags(item.knowledge_tags),
            question_type=item.question_type,
            difficulty_level=item.difficulty_level,
            difficulty_label=item.difficulty_label,
            difficulty_confidence=item.difficulty_confidence,
            difficulty_reason=item.difficulty_reason,
            difficulty_model=item.difficulty_model,
            difficulty_evaluated_at=item.difficulty_evaluated_at,
            metadata_status=item.metadata_status,
            metadata_error=item.metadata_error,
            metadata_started_at=item.metadata_started_at,
            metadata_finished_at=item.metadata_finished_at,
            origin_image=item.origin_image,
            image_url=build_question_image_url(item.id),
            created_at=item.created_at,
        )
        for item in questions
    ]


@router.get("/questions/trash", response_model=List[QuestionListItem])
def list_question_trash(db: Session = Depends(get_db), current_user: User = Depends(require_active_user)):
    now = datetime.now(timezone.utc)
    return [QuestionListItem.model_validate(q) for q in db.query(Question).filter(Question.user_id == current_user.id, Question.deleted_at.isnot(None), Question.purge_at > now, Question.purged_at.is_(None)).order_by(Question.deleted_at.desc()).all()]


@router.get("/questions/trash/{question_id}", response_model=QuestionDetail)
def get_question_trash(question_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_active_user)):
    q = db.query(Question).filter(Question.id == question_id, Question.user_id == current_user.id, Question.deleted_at.isnot(None), Question.purge_at > datetime.now(timezone.utc), Question.purged_at.is_(None)).first()
    if not q:
        raise HTTPException(404, NOT_FOUND_MESSAGE)
    return QuestionDetail.model_validate(q)


@router.get("/questions/{question_id}", response_model=QuestionDetail)
def get_question_detail(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    question = db.query(Question).filter(Question.id == question_id, Question.user_id == current_user.id, Question.deleted_at.is_(None), Question.purged_at.is_(None)).first()
    if not question:
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)

    return QuestionDetail(
        id=question.id,
        content=question.content,
        answer=question.answer,
        analysis=question.analysis,
        current_revision_no=(latest_question_revision(db, question.id).rev_no if latest_question_revision(db, question.id) else None),
        deleted_at=question.deleted_at,
        purge_at=question.purge_at,
        purged_at=question.purged_at,
        knowledge_tags=normalize_tags(question.knowledge_tags),
        question_type=question.question_type,
        difficulty_level=question.difficulty_level,
        difficulty_label=question.difficulty_label,
        difficulty_confidence=question.difficulty_confidence,
        difficulty_reason=question.difficulty_reason,
        difficulty_model=question.difficulty_model,
        difficulty_evaluated_at=question.difficulty_evaluated_at,
        metadata_status=question.metadata_status,
        metadata_error=question.metadata_error,
        metadata_started_at=question.metadata_started_at,
        metadata_finished_at=question.metadata_finished_at,
        origin_image=question.origin_image,
        image_url=build_question_image_url(question.id),
        created_at=question.created_at,
    )


@router.post("/questions/{question_id}/trash")
def move_question_to_trash(question_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_active_user)):
    q = trash_question(db, current_user, question_id)
    return {"success": True, "question_id": q.id, "deleted_at": q.deleted_at, "purge_at": q.purge_at}

@router.post("/questions/{question_id}/restore")
def restore_question_from_trash(question_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_active_user)):
    q = restore_question(db, current_user, question_id)
    return {"success": True, "question_id": q.id}

@router.delete("/questions/{question_id}/permanent")
def permanently_delete_question(question_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_active_user)):
    q = permanent_question(db, current_user, question_id)
    return {"success": True, "question_id": q.id, "purged_at": q.purged_at}


def list_question_trash(db: Session = Depends(get_db), current_user: User = Depends(require_active_user)):
    now = datetime.now(timezone.utc)
    return [QuestionListItem.model_validate(q) for q in db.query(Question).filter(Question.user_id == current_user.id, Question.deleted_at.isnot(None), Question.purge_at > now, Question.purged_at.is_(None)).order_by(Question.deleted_at.desc()).all()]


@router.get("/questions/{question_id}/image")
def get_question_image(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)
    if question.user_id != current_user.id:
        raise HTTPException(status_code=403, detail=FORBIDDEN_MESSAGE)
    if question.purged_at or (question.purge_at and question.purge_at <= datetime.now(timezone.utc)):
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)

    # Ownership is enforced above on the Question row on purpose: SourceAsset rows are
    # deduplicated by sha256 across users, so the asset itself carries no owner
    # semantics and only marks where the shared bytes live. A saved multi-question
    # draft keeps the page asset and question-relative bbox on its revision; use those
    # together so each question gets its own region instead of the whole page.
    revision = (
        db.query(QuestionRevision)
        .filter(QuestionRevision.question_id == question.id)
        .order_by(QuestionRevision.rev_no.desc(), QuestionRevision.id.desc())
        .first()
    )
    source_reference = question.origin_image
    crop_bbox = None
    if revision is not None:
        crop_bbox = revision.crop_bbox
        if revision.source_asset is not None:
            source_reference = revision.source_asset.normalized_path or revision.source_asset.original_path

    file_path = resolve_upload_file_path(source_reference)
    if not file_path:
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)

    # None is the legacy no-revision/no-bbox case and deliberately falls back to the
    # historical origin image. {} is the established full-image marker. Any other
    # malformed bbox is fail-closed rather than leaking the page or returning 500.
    if crop_bbox is None:
        return FileResponse(file_path)
    try:
        content, media_type = render_draft_image(file_path, crop_bbox)
    except Exception:
        logger.warning("Invalid or unreadable question crop question_id={}", question.id)
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/questions/{question_id}/figure")
def get_question_figure(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)
    if question.user_id != current_user.id:
        raise HTTPException(status_code=403, detail=FORBIDDEN_MESSAGE)
    if question.purged_at or (question.purge_at and question.purge_at <= datetime.now(timezone.utc)):
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)

    # Same ownership rationale as get_question_image (#58): the Question row
    # carries ownership; the referenced asset only marks where bytes live.
    file_path = resolve_upload_file_path(question.figure_image)
    if not file_path:
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)

    return FileResponse(file_path)
