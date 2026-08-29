from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.paper import Paper, PaperItem
from app.models.question import Question
from app.models.question_revision import QuestionRevision
from app.models.user import User
from app.services.question_content import (
    adapt_section_snapshot,
    legacy_figure_stable_id,
    project_legacy_text,
)
from app.schemas.paper import (
    PaperCreate,
    PaperExistingItemUpdate,
    PaperItemRead,
    PaperListItem,
    PaperRead,
    PaperUpdate,
)

NOT_FOUND_MESSAGE = "\u8d44\u6e90\u4e0d\u5b58\u5728"
PAPER_EMPTY_ITEMS_MESSAGE = "\u8bd5\u5377\u81f3\u5c11\u9700\u8981\u4e00\u9053\u9898"
PAPER_DUPLICATE_QUESTION_MESSAGE = "\u540c\u4e00\u5f20\u8bd5\u5377\u4e0d\u80fd\u91cd\u590d\u6dfb\u52a0\u540c\u4e00\u9898"
PAPER_NOT_DRAFT_MESSAGE = "\u53ea\u6709\u8349\u7a3f\u72b6\u6001\u7684\u8bd5\u5377\u53ef\u4ee5\u7f16\u8f91"
PAPER_ITEM_MISMATCH_MESSAGE = "\u8bd5\u5377\u9898\u76ee\u4e0d\u5b58\u5728\u6216\u4e0d\u5c5e\u4e8e\u5f53\u524d\u8bd5\u5377"
PAPER_EMPTY_CONTENT_MESSAGE = "\u8bd5\u5377\u9898\u5e72\u4e0d\u80fd\u4e3a\u7a7a"


def _latest_revision(db: Session, question_id: int) -> Optional[QuestionRevision]:
    return (
        db.query(QuestionRevision)
        .filter(QuestionRevision.question_id == question_id)
        .order_by(QuestionRevision.rev_no.desc(), QuestionRevision.id.desc())
        .first()
    )


def _text_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _figure_snapshot(question: Question, revision: Optional[QuestionRevision]) -> Optional[str]:
    """Freeze the question's figure reference at snapshot time (#59).

    Mirrors the expression used when #58 writes the figure onto the
    question/revision pair, so the frozen value stays byte-identical to the
    source. The revision's asset wins (same precedence as text snapshots read
    from the latest revision); questions without a revision figure fall back to
    the question-level reference.
    """
    if revision is not None and revision.figure_asset is not None:
        return revision.figure_asset.normalized_path or revision.figure_asset.original_path
    return question.figure_image or None


def _snapshot_from_question(db: Session, question: Question) -> dict[str, Any]:
    revision = _latest_revision(db, question.id)
    revision_content = revision.content if revision and isinstance(revision.content, dict) else None

    if revision_content:
        legacy_content = revision_content.get("text") or revision_content.get("content") or question.content
        legacy_answer = revision_content.get("answer", question.answer)
        legacy_analysis = revision_content.get("analysis", question.analysis)
        knowledge_tags_snapshot = (
            revision_content.get("knowledge_tags")
            or revision_content.get("knowledge")
            or question.knowledge_tags
        )
    else:
        legacy_content = question.content
        legacy_answer = question.answer
        legacy_analysis = question.analysis
        knowledge_tags_snapshot = question.knowledge_tags

    section_snapshot = adapt_section_snapshot(
        section_snapshot=revision.section_snapshot if revision else question.section_snapshot,
        content=legacy_content,
        answer=legacy_answer,
        analysis=legacy_analysis,
        seed=f"revision:{revision.id}" if revision else f"question:{question.id}",
        legacy_figure_id=(
            legacy_figure_stable_id(question.id)
            if revision and revision.figure_asset_id
            else None
        ),
    )
    projected = project_legacy_text(section_snapshot)
    content_snapshot = _text_value(projected["content"])
    answer_snapshot = _text_value(projected["answer"])
    analysis_snapshot = _text_value(projected["analysis"])

    metadata_ready = question.metadata_status == "ready" and question.difficulty_level is not None

    return {
        "question_revision_id": revision.id if revision else None,
        "content_snapshot": content_snapshot or "",
        "answer_snapshot": answer_snapshot,
        "analysis_snapshot": analysis_snapshot,
        "knowledge_tags_snapshot": knowledge_tags_snapshot or [],
        "question_type_snapshot": question.question_type if metadata_ready else None,
        "difficulty_level_snapshot": question.difficulty_level if metadata_ready else None,
        "difficulty_label_snapshot": question.difficulty_label if metadata_ready else None,
        "figure_image_snapshot": _figure_snapshot(question, revision),
    }


def _total_score(items: list[PaperItem]) -> float:
    return float(sum(item.score or 0 for item in items))


def _build_paper_read(paper: Paper) -> PaperRead:
    items = list(paper.items or [])
    return PaperRead(
        id=paper.id,
        title=paper.title,
        description=paper.description,
        status=paper.status,
        item_count=len(items),
        total_score=_total_score(items),
        items=[
            PaperItemRead(
                id=item.id,
                question_id=item.question_id,
                position=item.position,
                score=item.score,
                content_snapshot=item.content_snapshot,
                answer_snapshot=item.answer_snapshot,
                analysis_snapshot=item.analysis_snapshot,
                knowledge_tags_snapshot=item.knowledge_tags_snapshot,
                question_type_snapshot=item.question_type_snapshot,
                difficulty_level_snapshot=item.difficulty_level_snapshot,
                difficulty_label_snapshot=item.difficulty_label_snapshot,
                figure_image_snapshot=item.figure_image_snapshot,
            )
            for item in items
        ],
        created_at=paper.created_at,
        updated_at=paper.updated_at,
    )


def create_paper(db: Session, current_user: User, payload: PaperCreate) -> PaperRead:
    if not payload.items:
        raise HTTPException(status_code=400, detail=PAPER_EMPTY_ITEMS_MESSAGE)

    question_ids = [item.question_id for item in payload.items]
    if len(question_ids) != len(set(question_ids)):
        raise HTTPException(status_code=409, detail=PAPER_DUPLICATE_QUESTION_MESSAGE)

    questions = (
        db.query(Question)
        .filter(Question.user_id == current_user.id, Question.id.in_(question_ids), Question.deleted_at.is_(None), Question.purged_at.is_(None))
        .all()
    )
    questions_by_id = {question.id: question for question in questions}
    if len(questions_by_id) != len(question_ids):
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)

    paper = Paper(
        user_id=current_user.id,
        title=payload.title,
        description=payload.description,
        status="draft",
    )
    db.add(paper)
    db.flush()

    for index, item_payload in enumerate(payload.items, start=1):
        question = questions_by_id[item_payload.question_id]
        snapshot = _snapshot_from_question(db, question)
        db.add(
            PaperItem(
                paper_id=paper.id,
                question_id=question.id,
                position=index,
                score=item_payload.score if item_payload.score is not None else 0,
                **snapshot,
            )
        )

    db.commit()
    db.refresh(paper)
    return _build_paper_read(paper)


def update_paper(db: Session, current_user: User, paper_id: int, payload: PaperUpdate) -> PaperRead:
    paper = db.query(Paper).filter(Paper.id == paper_id, Paper.user_id == current_user.id).first()
    if not paper:
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)
    if paper.status != "draft":
        raise HTTPException(status_code=409, detail=PAPER_NOT_DRAFT_MESSAGE)

    item_payloads = list(payload.items)
    question_ids = [item.question_id for item in item_payloads]
    if len(question_ids) != len(set(question_ids)):
        raise HTTPException(status_code=409, detail=PAPER_DUPLICATE_QUESTION_MESSAGE)

    current_items = list(paper.items or [])
    current_items_by_id = {item.id: item for item in current_items}
    retained_item_ids: set[int] = set()
    new_question_ids: list[int] = []

    for item_payload in item_payloads:
        if isinstance(item_payload, PaperExistingItemUpdate):
            current_item = current_items_by_id.get(item_payload.id)
            if not current_item or current_item.question_id != item_payload.question_id:
                raise HTTPException(status_code=404, detail=PAPER_ITEM_MISMATCH_MESSAGE)
            if item_payload.id in retained_item_ids:
                raise HTTPException(status_code=409, detail=PAPER_DUPLICATE_QUESTION_MESSAGE)
            retained_item_ids.add(item_payload.id)
        else:
            new_question_ids.append(item_payload.question_id)

    questions_by_id: dict[int, Question] = {}
    if new_question_ids:
        questions = (
            db.query(Question)
            .filter(
                Question.user_id == current_user.id,
                Question.id.in_(new_question_ids),
                Question.deleted_at.is_(None),
                Question.purged_at.is_(None),
            )
            .all()
        )
        questions_by_id = {question.id: question for question in questions}
        if len(questions_by_id) != len(new_question_ids):
            raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)

    new_snapshots: dict[int, dict[str, Any]] = {}
    for item_payload in item_payloads:
        if isinstance(item_payload, PaperExistingItemUpdate):
            continue
        snapshot = _snapshot_from_question(db, questions_by_id[item_payload.question_id])
        for field_name in ("content_snapshot", "answer_snapshot", "analysis_snapshot"):
            if field_name in item_payload.model_fields_set:
                snapshot[field_name] = getattr(item_payload, field_name)
        if not snapshot["content_snapshot"] or not snapshot["content_snapshot"].strip():
            raise HTTPException(status_code=400, detail=PAPER_EMPTY_CONTENT_MESSAGE)
        new_snapshots[item_payload.question_id] = snapshot

    try:
        paper.title = payload.title
        paper.description = payload.description

        removed_items = [item for item in current_items if item.id not in retained_item_ids]
        for item in removed_items:
            db.delete(item)

        max_position = max(
            max((item.position for item in current_items), default=0),
            len(item_payloads),
        )
        retained_items = [current_items_by_id[item.id] for item in item_payloads if isinstance(item, PaperExistingItemUpdate)]
        for temporary_index, item in enumerate(retained_items, start=1):
            item.position = max_position + temporary_index
        db.flush()

        new_items: list[tuple[int, Any]] = []
        for position, item_payload in enumerate(item_payloads, start=1):
            if isinstance(item_payload, PaperExistingItemUpdate):
                item = current_items_by_id[item_payload.id]
                item.position = position
                item.score = item_payload.score
                item.content_snapshot = item_payload.content_snapshot
                item.answer_snapshot = item_payload.answer_snapshot
                item.analysis_snapshot = item_payload.analysis_snapshot
                continue

            new_items.append((position, item_payload))

        db.flush()

        for position, item_payload in new_items:
            question = questions_by_id[item_payload.question_id]
            db.add(
                PaperItem(
                    paper_id=paper.id,
                    question_id=question.id,
                    position=position,
                    score=item_payload.score,
                    **new_snapshots[item_payload.question_id],
                )
            )

        paper.updated_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(paper)
    return _build_paper_read(paper)


def get_paper(db: Session, current_user: User, paper_id: int) -> PaperRead:
    paper = db.query(Paper).filter(Paper.id == paper_id, Paper.user_id == current_user.id).first()
    if not paper:
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)
    return _build_paper_read(paper)


def list_papers(db: Session, current_user: User) -> list[PaperListItem]:
    papers = (
        db.query(Paper)
        .filter(Paper.user_id == current_user.id)
        .order_by(Paper.created_at.desc(), Paper.id.desc())
        .all()
    )
    result: list[PaperListItem] = []
    for paper in papers:
        items = list(paper.items or [])
        result.append(
            PaperListItem(
                id=paper.id,
                title=paper.title,
                status=paper.status,
                item_count=len(items),
                total_score=_total_score(items),
                created_at=paper.created_at,
                updated_at=paper.updated_at,
            )
        )
    return result
