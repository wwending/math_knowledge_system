from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.paper import Paper, PaperItem
from app.models.user import User
from app.schemas.paper_render import (
    PaperRenderAnswerArea,
    PaperRenderItem,
    PaperRenderKnowledgeTag,
    PaperRenderLayout,
    PaperRenderModel,
    PaperRenderPaperMeta,
    PaperRenderRequest,
    PaperRenderSection,
)
from app.services.paper_service import NOT_FOUND_MESSAGE


QUESTION_TYPE_LABELS = {
    "single_choice": "单选题",
    "multiple_choice": "多选题",
    "fill_blank": "填空题",
    "solution": "解答题",
    "judge": "判断题",
    "unknown": "未分类",
}


def _total_score(items: list[PaperItem]) -> float:
    return float(sum(item.score or 0 for item in items))


def _normalize_knowledge_tags(raw_tags: Any) -> list[PaperRenderKnowledgeTag]:
    if not raw_tags:
        return []

    normalized: list[PaperRenderKnowledgeTag] = []
    source = raw_tags if isinstance(raw_tags, list) else [raw_tags]

    for raw_tag in source:
        label = ""
        score = None
        if isinstance(raw_tag, str):
            label = raw_tag.strip()
        elif isinstance(raw_tag, dict):
            label = str(raw_tag.get("label") or raw_tag.get("name") or "").strip()
            raw_score = raw_tag.get("score")
            if isinstance(raw_score, (int, float)):
                score = float(raw_score)
        elif raw_tag is not None:
            label = str(raw_tag).strip()

        if label:
            normalized.append(PaperRenderKnowledgeTag(label=label, score=score))

    return normalized


def _question_type_key(item: PaperItem) -> str:
    question_type = (item.question_type_snapshot or "").strip()
    return question_type if question_type else "unknown"


def _answer_area(payload: PaperRenderRequest) -> PaperRenderAnswerArea | None:
    if payload.answer_area_mode != "after_each_question":
        return None
    return PaperRenderAnswerArea(mode="after_each_question", lines=4)


def build_paper_render_model(db: Session, current_user: User, paper_id: int, payload: PaperRenderRequest) -> PaperRenderModel:
    paper = db.query(Paper).filter(Paper.id == paper_id, Paper.user_id == current_user.id).first()
    if not paper:
        raise HTTPException(status_code=404, detail=NOT_FOUND_MESSAGE)

    sorted_items = sorted(list(paper.items or []), key=lambda item: (item.position, item.id))
    grouped: dict[str, list[PaperRenderItem]] = {}
    section_order: list[str] = []

    for display_number, item in enumerate(sorted_items, start=1):
        question_type = _question_type_key(item)
        if question_type not in grouped:
            grouped[question_type] = []
            section_order.append(question_type)

        grouped[question_type].append(
            PaperRenderItem(
                paper_item_id=item.id,
                question_id=item.question_id,
                position=item.position,
                display_number=display_number,
                score=item.score,
                content=item.content_snapshot or "",
                question_type=question_type,
                question_type_label=QUESTION_TYPE_LABELS.get(question_type, question_type),
                knowledge_tags=_normalize_knowledge_tags(item.knowledge_tags_snapshot),
                answer_area=_answer_area(payload),
            )
        )

    return PaperRenderModel(
        template_type=payload.template_type,
        version=payload.version,
        paper_size=payload.paper_size,
        group_by=payload.group_by,
        sort_by=payload.sort_by,
        answer_area_mode=payload.answer_area_mode,
        paper=PaperRenderPaperMeta(
            id=paper.id,
            title=paper.title,
            description=paper.description,
            status=paper.status,
            item_count=len(sorted_items),
            total_score=_total_score(sorted_items),
        ),
        layout=PaperRenderLayout(),
        sections=[
            PaperRenderSection(
                key=key,
                title=QUESTION_TYPE_LABELS.get(key, key),
                items=grouped[key],
            )
            for key in section_order
        ],
    )
