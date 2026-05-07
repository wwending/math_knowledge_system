import hashlib
import json
import mimetypes
import os
import shutil
import time
import uuid
from typing import Any, List, Optional

import fitz
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
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
from app.schemas.draft import DraftCreate, DraftDetail, DraftRecognizeResponse, DraftSaveToBankResponse
from app.schemas.ocr import OCRResponse
from app.schemas.question import KnowledgeTag, QuestionDetail, QuestionListItem, QuestionUpdate
from app.services.draft_state import transition_draft_status
from app.services.llm import nlp_service
from app.services.ocr_engine import ocr_service


router = APIRouter()

NOT_FOUND_MESSAGE = "\u8d44\u6e90\u4e0d\u5b58\u5728"
FORBIDDEN_MESSAGE = "\u65e0\u6743\u8bbf\u95ee\u8be5\u8d44\u6e90"
QUESTION_UPDATED_MESSAGE = "\u9898\u76ee\u5185\u5bb9\u5df2\u66f4\u65b0"
PDF_ONLY_MESSAGE = "\u8bf7\u4e0a\u4f20 PDF \u6587\u4ef6"
PDF_PARSE_FAILED_MESSAGE = "\u672a\u80fd\u89e3\u6790 PDF \u6587\u4ef6"
UPLOAD_SAVE_FAILED_MESSAGE = "\u4e0a\u4f20\u6587\u4ef6\u4fdd\u5b58\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5"
QUESTION_SAVE_FAILED_MESSAGE = "\u9898\u76ee\u4fdd\u5b58\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5"
DRAFT_READY_REQUIRED_MESSAGE = "\u53ea\u6709\u5df2\u8bc6\u522b\u5b8c\u6210\u7684 Draft \u53ef\u4ee5\u4fdd\u5b58\u5165\u9898\u5e93"


class SourceAssetResponse(BaseModel):
    asset_id: int
    kind: str
    mime: str
    size_bytes: int
    width: Optional[int] = None
    height: Optional[int] = None
    sha256: str


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


def _build_draft_detail(draft: Draft) -> DraftDetail:
    return DraftDetail(
        id=draft.id,
        source_asset_id=draft.source_asset_id,
        crop_bbox=draft.crop_bbox,
        status=draft.status,
        current_content=draft.current_content,
        content=_content_text(draft.current_content),
        knowledge_tags=_content_tags(draft.current_content),
        last_ocr_run_id=draft.last_ocr_run_id,
        last_llm_run_id=draft.last_llm_run_id,
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
        raise HTTPException(status_code=409, detail="Asset already exists")
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


@router.post("/drafts/{draft_id}/recognize", response_model=DraftRecognizeResponse)
def recognize_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    draft = _ensure_owned_draft(db, draft_id, current_user.id)
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
    try:
        ocr_result = ocr_service.recognize(file_path)
    except Exception:
        logger.exception("Unexpected Draft OCR crash draft_id={} user_id={}", draft.id, current_user.id)
        ocr_result = {
            "success": False,
            "content": "",
            "cost_seconds": 0.0,
            "error_type": "service_error",
            "error": "\u6587\u5b57\u8bc6\u522b\u670d\u52a1\u8c03\u7528\u5931\u8d25",
            "detail": "ocr_unexpected_error",
        }

    raw_content = (ocr_result.get("content") or "").strip()
    ocr_run = OCRRun(
        draft_id=draft.id,
        provider="baidu",
        endpoint=getattr(ocr_service, "ocr_url", None),
        request_params_redacted={"source_asset_id": asset.id, "crop_bbox": draft.crop_bbox},
        response_raw_json=ocr_result,
        parsed_blocks=[{"text": raw_content}] if raw_content else [],
        latency_ms=int(float(ocr_result.get("cost_seconds") or 0) * 1000),
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

    if llm_result.get("success"):
        final_content = llm_result.get("corrected_text", raw_content) or raw_content
        knowledge_tags = _normalize_llm_tags(llm_result.get("tags", []))
    else:
        partial_success = True
        warning = llm_result.get("error") or "\u667a\u80fd\u6574\u7406\u5931\u8d25\uff0c\u5df2\u4fdd\u7559\u539f\u59cb\u8bc6\u522b\u7ed3\u679c"
        final_content = llm_result.get("corrected_text", raw_content) or raw_content
        knowledge_tags = _normalize_llm_tags(llm_result.get("tags", []))

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
        },
        commit=True,
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
    db: Session = Depends(get_db),
    current_user: User = Depends(require_active_user),
):
    draft = _ensure_owned_draft(db, draft_id, current_user.id)
    if draft.status != DraftStatus.DRAFT_READY:
        raise HTTPException(status_code=409, detail=DRAFT_READY_REQUIRED_MESSAGE)

    content_text = _content_text(draft.current_content).strip()
    knowledge_tags = [tag.model_dump() for tag in _content_tags(draft.current_content)]

    question = Question(
        user_id=current_user.id,
        content=content_text,
        knowledge_tags=knowledge_tags,
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

    detail = _build_draft_detail(draft)
    return DraftSaveToBankResponse(
        **detail.model_dump(),
        question_id=question.id,
        question_revision_id=revision.id,
        rev_no=revision.rev_no,
    )


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
            knowledge_tags = _normalize_llm_tags(llm_result.get("tags", []))
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
            knowledge_tags = _normalize_llm_tags(llm_result.get("tags", []))

    try:
        new_question = Question(
            origin_image=unique_filename,
            user_id=current_user.id,
            content=final_content,
            knowledge_tags=knowledge_tags,
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
        origin_image=question.origin_image,
        image_url=build_upload_image_url(question.origin_image),
        created_at=question.created_at,
    )
