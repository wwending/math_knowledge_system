import time
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.question import Question
from app.services.llm import nlp_service


def _short_error(result: dict[str, Any] | None, exc: Exception | None = None) -> str:
    if result:
        error_type = result.get("error_type")
        detail = result.get("detail")
        if error_type == "timeout":
            return "timeout"
        if error_type == "invalid_response":
            return "invalid_json"
        if error_type in {"service_error", "service_unavailable", "auth_failed"}:
            return "api_error"
        if isinstance(detail, str) and "deepseek_non_json" in detail:
            return "invalid_json"
        if isinstance(detail, str) and "deepseek_api" in detail:
            return "api_error"
        for key in ("error_type", "detail", "error"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()[:120]
    if exc:
        return exc.__class__.__name__[:120]
    return "metadata_failed"


def _apply_success(question: Question, result: dict[str, Any], now: datetime) -> None:
    difficulty = result.get("difficulty")
    question.question_type = result.get("question_type") or "unknown"
    if isinstance(difficulty, dict):
        question.difficulty_level = difficulty.get("level")
        question.difficulty_label = difficulty.get("label")
        question.difficulty_confidence = difficulty.get("confidence")
        question.difficulty_reason = difficulty.get("reason")
        question.difficulty_model = settings.DEEPSEEK_MODEL
        question.difficulty_evaluated_at = now
    question.metadata_status = "ready"
    question.metadata_error = None
    question.metadata_finished_at = now


def evaluate_question_metadata_task(question_id: int) -> None:
    started_at = time.time()
    db = SessionLocal()
    status = "failed"
    question_type = None
    difficulty_level = None
    error = None
    load_ms = 0
    prompt_ms = 0
    api_ms = 0
    parse_ms = 0
    db_ms = 0
    question = None
    try:
        load_started_at = time.time()
        question = db.query(Question).filter(Question.id == question_id).first()
        load_ms = int((time.time() - load_started_at) * 1000)
        if not question:
            status = "skipped"
            error = "not_found"
            return

        generation = question.metadata_generation or 0
        now = datetime.now(timezone.utc)
        if question.deleted_at or question.purged_at: status = "skipped"; error = "lifecycle"; return
        question.metadata_status = "processing"
        question.metadata_started_at = now
        question.metadata_error = None
        db_started_at = time.time()
        db.commit()
        db_ms += int((time.time() - db_started_at) * 1000)

        prompt_started_at = time.time()
        content = (question.content or "").strip()
        prompt_ms = int((time.time() - prompt_started_at) * 1000)
        if not content:
            question.metadata_status = "skipped"
            question.metadata_error = "empty_content"
            question.metadata_finished_at = datetime.now(timezone.utc)
            db_started_at = time.time()
            db.commit()
            db_ms += int((time.time() - db_started_at) * 1000)
            status = "skipped"
            error = "empty_content"
            return

        api_started_at = time.time()
        result = nlp_service.evaluate_question_metadata(content)
        api_ms = int((time.time() - api_started_at) * 1000)
        perf = result.get("_perf") if isinstance(result, dict) else None
        if isinstance(perf, dict):
            prompt_ms = int(perf.get("prompt_ms") or prompt_ms)
            api_ms = int(perf.get("api_ms") or api_ms)
            parse_ms = int(perf.get("parse_ms") or 0)
        finished_at = datetime.now(timezone.utc)
        db.refresh(question)
        if question.metadata_generation != generation or question.deleted_at or question.purged_at:
            status = "skipped"; error = "stale_generation"; return
        if result.get("success"):
            _apply_success(question, result, finished_at)
            status = "ready"
            question_type = question.question_type
            difficulty_level = question.difficulty_level
        else:
            question.metadata_status = "failed"
            question.metadata_error = _short_error(result)
            question.metadata_finished_at = finished_at
            status = "failed"
            error = question.metadata_error
        db_started_at = time.time()
        db.commit()
        db_ms += int((time.time() - db_started_at) * 1000)
    except Exception as exc:
        logger.exception("Question metadata evaluation failed question_id={}", question_id)
        if api_ms == 0:
            api_ms = int((time.time() - locals().get("api_started_at", started_at)) * 1000)
        db.rollback()
        try:
            question = db.query(Question).filter(Question.id == question_id).first()
            if question:
                question.metadata_status = "failed"
                question.metadata_error = _short_error(None, exc)
                question.metadata_finished_at = datetime.now(timezone.utc)
                db_started_at = time.time()
                db.commit()
                db_ms += int((time.time() - db_started_at) * 1000)
                error = question.metadata_error
        except Exception:
            db.rollback()
            logger.exception("Failed to persist question metadata failure question_id={}", question_id)
    finally:
        logger.info(
            "[QuestionMetadataPerf] question_id={} load_ms={} prompt_ms={} api_ms={} parse_ms={} db_ms={} total_ms={} model={} status={} question_type={} difficulty_level={} error={}",
            question_id,
            load_ms,
            prompt_ms,
            api_ms,
            parse_ms,
            db_ms,
            int((time.time() - started_at) * 1000),
            settings.DEEPSEEK_MODEL,
            status,
            question_type,
            difficulty_level,
            error,
        )
        db.close()
