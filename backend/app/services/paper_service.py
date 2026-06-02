from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.paper import Paper, PaperItem
from app.models.question import Question
from app.models.question_revision import QuestionRevision
from app.models.user import User
from app.schemas.paper import PaperCreate, PaperItemRead, PaperListItem, PaperRead

NOT_FOUND_MESSAGE = "\u8d44\u6e90\u4e0d\u5b58\u5728"
PAPER_EMPTY_ITEMS_MESSAGE = "\u8bd5\u5377\u81f3\u5c11\u9700\u8981\u4e00\u9053\u9898"
PAPER_DUPLICATE_QUESTION_MESSAGE = "\u540c\u4e00\u5f20\u8bd5\u5377\u4e0d\u80fd\u91cd\u590d\u6dfb\u52a0\u540c\u4e00\u9898"


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


def _snapshot_from_question(db: Session, question: Question) -> dict[str, Any]:
    revision = _latest_revision(db, question.id)
    revision_content = revision.content if revision and isinstance(revision.content, dict) else None

    if revision_content:
        content_snapshot = _text_value(
            revision_content.get("text") or revision_content.get("content") or question.content
        )
        answer_snapshot = _text_value(revision_content.get("answer"))
        analysis_snapshot = _text_value(revision_content.get("analysis"))
        knowledge_tags_snapshot = (
            revision_content.get("knowledge_tags")
            or revision_content.get("knowledge")
            or question.knowledge_tags
        )
    else:
        content_snapshot = _text_value(question.content)
        answer_snapshot = None
        analysis_snapshot = None
        knowledge_tags_snapshot = question.knowledge_tags

    return {
        "question_revision_id": revision.id if revision else None,
        "content_snapshot": content_snapshot or "",
        "answer_snapshot": answer_snapshot,
        "analysis_snapshot": analysis_snapshot,
        "knowledge_tags_snapshot": knowledge_tags_snapshot or [],
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
        .filter(Question.user_id == current_user.id, Question.id.in_(question_ids))
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
