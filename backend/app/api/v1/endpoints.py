import hashlib
import json
import mimetypes
import os
import re
import shutil
import time
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional
from urllib.parse import quote

import fitz
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Response, UploadFile
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
    DraftEventType,
    DraftStatus,
)
from app.core.database import get_db
from app.models.draft import Draft
from app.models.draft_event import DraftEvent
from app.models.llm_run import LLMRun
from app.models.ocr_run import OCRRun
from app.models.question import Question
from app.models.question_revision import QuestionRevision
from app.models.source_asset import SourceAsset
from app.models.user import User
from app.schemas.draft import (
    DraftCreate,
    DraftDetail,
    DraftRecognizeResponse,
    DraftSaveToBankResponse,
    DraftUpdate,
    RecognitionDebug,
)
from app.schemas.ocr import OCRResponse
from app.schemas.paper import PaperCreate, PaperListItem, PaperRead
from app.schemas.paper_render import PaperRenderModel, PaperRenderRequest
from app.schemas.question import KnowledgeTag, QuestionDetail, QuestionListItem, QuestionUpdate
from app.services.draft_state import transition_draft_status
from app.services.llm import nlp_service
from app.services.ocr_engine import ocr_service
from app.services.ocr_providers.base import OCRResult
from app.services.ocr_service import ocr_service as draft_ocr_service
from app.services.paper_service import create_paper, get_paper, list_papers
from app.services.paper_render_service import build_paper_render_model
from app.services.paper_html_renderer import PaperHtmlRenderError, render_paper_html
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


def build_upload_image_url(raw_path: Optional[str]) -> Optional[str]:
    if not raw_path:
        return None

    normalized_path = str(raw_path).strip()
    if not normalized_path:
        return None

    if normalized_path.startswith(("http://", "https://")):
        return normalized_path

    if normalized_path.startswith(f"{settings.STATIC_URL_PREFIX_NORMALIZED}/"):
        return normalized_path

    upload_relative_dir = os.path.relpath(
        str(settings.UPLOAD_DIR_PATH),
        str(settings.STATIC_DIR_PATH),
    ).replace("\\", "/").strip("./")

    relative_path = normalized_path.lstrip("/")
    if relative_path.startswith("static/"):
        relative_path = relative_path[len("static/"):]
    elif upload_relative_dir and not relative_path.startswith(f"{upload_relative_dir}/"):
        relative_path = f"{upload_relative_dir}/{os.path.basename(relative_path)}"

    return f"{settings.STATIC_URL_PREFIX_NORMALIZED}/{relative_path.lstrip('/')}"


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
    questions = db.query(Question).filter(Question.user_id == current_user.id).all()

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
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)
    if question.user_id != current_user.id:
        raise HTTPException(status_code=403, detail=FORBIDDEN_MESSAGE)

    question.content = question_update.content
    db.commit()
    db.refresh(question)
    return {"success": True, "msg": QUESTION_UPDATED_MESSAGE}


@router.get("/history", response_model=List[OCRResponse])
def read_history(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    questions = (
        db.query(Question)
        .filter(Question.user_id == current_user.id)
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
                image_url=build_upload_image_url(question.origin_image),
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

    with open(pdf_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    image_list = []
    try:
        document = fitz.open(pdf_path)
        for page_index in range(len(document)):
            page = document.load_page(page_index)
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
            img_name = f"{task_id}_page_{page_index}.jpg"
            img_path = os.path.join(pdf_temp_dir, img_name)
            pix.save(img_path)
            image_list.append(f"pdf_temp/{img_name}")
        document.close()
        return {"success": True, "total_pages": len(image_list), "images": image_list}
    except Exception:
        logger.exception("PDF parse failed user_id={} path={}", current_user.id, pdf_path)
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
        crop_bbox=payload.crop_bbox if payload.crop_bbox is not None else {},
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
    ocr_started_at = time.time()
    try:
        ocr_result = _ocr_result_to_legacy_payload(draft_ocr_service.recognize(file_path))
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
    ocr_ms = int((time.time() - ocr_started_at) * 1000)

    raw_content = (ocr_result.get("content") or "").strip()
    ocr_provider = ocr_result.get("provider") or getattr(draft_ocr_service, "provider_name", "unknown")
    ocr_latency_ms = int(ocr_result.get("latency_ms") or int(float(ocr_result.get("cost_seconds") or 0) * 1000))
    ocr_run = OCRRun(
        draft_id=draft.id,
        provider=ocr_provider,
        endpoint=getattr(draft_ocr_service, "endpoint", None),
        request_params_redacted={"source_asset_id": asset.id, "crop_bbox": draft.crop_bbox},
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
            "[DraftRecognizePerf] draft_id={} asset_id={} ocr_provider={} ocr_ms={} llm_text_ms={} total_ms={} model={} ocr_text_len={} corrected_text_len={} llm_fallback={} fallback_reason={} failure_stage={}",
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
        "[DraftRecognizePerf] draft_id={} asset_id={} ocr_provider={} ocr_ms={} llm_text_ms={} total_ms={} model={} ocr_text_len={} corrected_text_len={} llm_fallback={} fallback_reason={} failure_stage={}",
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
    )

    detail = _build_draft_detail(draft)
    return DraftRecognizeResponse(
        **detail.model_dump(),
        success=True,
        partial_success=partial_success,
        warning=warning,
        error_type="llm_failed" if partial_success else None,
    )


@router.post("/drafts/{draft_id}/save-to-bank", response_model=DraftSaveToBankResponse)
def save_draft_to_bank(
    draft_id: int,
    background_tasks: BackgroundTasks,
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
    try:
        printable_html = render_paper_html(render_model, options)
        pdf_bytes = pdf_generation_service.generate_pdf(printable_html, options)
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
    image_url = build_upload_image_url(unique_filename)

    logger.info("Saving recognize upload user_id={} path={}", current_user.id, file_path)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
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
        image_url=image_url,
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
    query = db.query(Question).filter(Question.user_id == current_user.id)
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
            image_url=build_upload_image_url(item.origin_image),
            created_at=item.created_at,
        )
        for item in questions
    ]


@router.get("/questions/{question_id}", response_model=QuestionDetail)
def get_question_detail(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)
    if question.user_id != current_user.id:
        raise HTTPException(status_code=403, detail=FORBIDDEN_MESSAGE)

    return QuestionDetail(
        id=question.id,
        content=question.content,
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
        image_url=build_upload_image_url(question.origin_image),
        created_at=question.created_at,
    )
