from __future__ import annotations

import hashlib
import math
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from PIL import Image
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.constants import (
    QUESTION_MAX_BLOCKS_PER_SECTION,
    QUESTION_MAX_FIGURE_BYTES,
    QUESTION_MAX_FIGURES,
    QUESTION_MAX_FIGURES_PER_IMAGE_AREA,
)
from app.core.files import resolve_upload_file_path
from app.models.question import Question
from app.models.question_figure import QuestionFigure, QuestionRevisionFigure
from app.models.question_revision import QuestionRevision
from app.models.source_asset import SourceAsset
from app.models.user import User
from app.schemas.question import (
    QuestionDocumentDetail,
    QuestionDocumentUpdate,
    QuestionDocumentUpdateResponse,
    QuestionFigureDetail,
)
from app.services.draft_image_service import compose_bbox_to_page, normalize_unit_bbox, pixel_crop_box
from app.services.question_content import (
    ContentSnapshotError,
    adapt_section_snapshot,
    normalize_v2_snapshot,
    project_legacy_text,
    snapshot_figure_ids,
)
from app.services.question_service import QUESTION_TYPES, _tags, owned


@dataclass
class DocumentIssue:
    code: str
    message: str
    section: str | None = None
    block_id: str | None = None
    block_index: int | None = None
    figure_id: str | None = None
    figure_index: int | None = None
    field: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {key: value for key, value in self.__dict__.items() if value is not None}


class QuestionDocumentInvalid(ValueError):
    def __init__(self, issues: list[DocumentIssue]):
        super().__init__(issues[0].message if issues else "题目内容未通过校验")
        self.issues = issues

    def detail(self) -> dict[str, Any]:
        return {
            "code": "question_document_invalid",
            "message": "题目内容未通过校验",
            "errors": [issue.as_dict() for issue in self.issues],
        }


@dataclass
class PreparedCrop:
    stable_id: str
    source_asset: SourceAsset
    source_bbox: list[float]
    temp_path: Path
    digest: str
    size_bytes: int
    width: int
    height: int


@dataclass
class FigureFile:
    path: Path
    mime: str


def _issue(code: str, message: str, **location: Any) -> QuestionDocumentInvalid:
    return QuestionDocumentInvalid([DocumentIssue(code=code, message=message, **location)])


def _rectangles_overlap(a: list[float], b: list[float], epsilon: float = 1e-9) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return min(ax + aw, bx + bw) - max(ax, bx) > epsilon and min(
        ay + ah, by + bh
    ) - max(ay, by) > epsilon


def _validate_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    try:
        normalized = normalize_v2_snapshot(snapshot)
    except ContentSnapshotError as exc:
        raise _issue("invalid_document", str(exc), field="sections") from exc

    for section_name, section in normalized["sections"].items():
        blocks = section["blocks"]
        if len(blocks) > QUESTION_MAX_BLOCKS_PER_SECTION:
            raise _issue(
                "too_many_blocks",
                f"每个区段最多包含 {QUESTION_MAX_BLOCKS_PER_SECTION} 个内容块",
                section=section_name,
                field=f"sections.{section_name}.blocks",
            )
        for block_index, block in enumerate(blocks):
            if block["kind"] != "image_area":
                continue
            placements = block["placements"]
            if len(placements) > QUESTION_MAX_FIGURES_PER_IMAGE_AREA:
                raise _issue(
                    "too_many_placements",
                    f"每个图片区最多放置 {QUESTION_MAX_FIGURES_PER_IMAGE_AREA} 张配图",
                    section=section_name,
                    block_id=block["id"],
                    block_index=block_index,
                )
            for index, placement in enumerate(placements):
                current = [placement[key] for key in ("x", "y", "width", "height")]
                for other in placements[index + 1 :]:
                    candidate = [other[key] for key in ("x", "y", "width", "height")]
                    if _rectangles_overlap(current, candidate):
                        raise _issue(
                            "placement_overlap",
                            "同一图片区中的配图摆放区域不能重叠",
                            section=section_name,
                            block_id=block["id"],
                            block_index=block_index,
                            figure_id=placement["figure_id"],
                        )
    return normalized


def _figure_url(question_id: int, stable_id: str) -> str:
    return f"{settings.API_V1_STR}/questions/{question_id}/figures/{stable_id}"


def _question_image_url(question_id: int) -> str:
    return f"{settings.API_V1_STR}/questions/{question_id}/image"


def _has_question_image(question: Question, revision: QuestionRevision | None) -> bool:
    return bool((revision and revision.source_asset_id) or question.origin_image)


def _latest_with_figures(db: Session, question_id: int) -> QuestionRevision | None:
    return (
        db.query(QuestionRevision)
        .options(
            selectinload(QuestionRevision.figure_links)
            .selectinload(QuestionRevisionFigure.figure)
            .selectinload(QuestionFigure.figure_asset),
            selectinload(QuestionRevision.source_asset),
        )
        .filter(QuestionRevision.question_id == question_id)
        .order_by(QuestionRevision.rev_no.desc(), QuestionRevision.id.desc())
        .first()
    )


def _build_detail(question: Question, revision: QuestionRevision | None) -> QuestionDocumentDetail:
    content = revision.content if revision and isinstance(revision.content, dict) else {}
    snapshot = adapt_section_snapshot(
        section_snapshot=revision.section_snapshot if revision else question.section_snapshot,
        content=content.get("text", content.get("content", question.content)),
        answer=content.get("answer", question.answer),
        analysis=content.get("analysis", question.analysis),
        seed=f"revision:{revision.id}" if revision else f"question:{question.id}",
    )
    projected = project_legacy_text(snapshot)
    links = list(revision.figure_links) if revision else []
    figures = []
    for link in links:
        figure = link.figure
        asset = figure.figure_asset
        figures.append(
            QuestionFigureDetail(
                id=figure.stable_id,
                url=_figure_url(question.id, figure.stable_id),
                mime=asset.mime,
                size_bytes=asset.size_bytes,
                width=asset.width,
                height=asset.height,
                source_crop_bbox=figure.source_crop_bbox,
            )
        )
    figures.sort(key=lambda item: item.id)
    has_question_image = _has_question_image(question, revision)
    return QuestionDocumentDetail(
        id=question.id,
        current_revision_no=revision.rev_no if revision else 0,
        sections=snapshot["sections"],
        figures=figures,
        content=projected["content"],
        answer=projected["answer"],
        analysis=projected["analysis"],
        knowledge_tags=_tags(content.get("knowledge_tags", question.knowledge_tags)),
        question_type=content.get("question_type", question.question_type),
        difficulty_level=content.get("difficulty_level", question.difficulty_level),
        has_question_image=has_question_image,
        has_figure=bool(figures),
        image_url=_question_image_url(question.id) if has_question_image else None,
    )


def get_document(db: Session, user: User, question_id: int) -> QuestionDocumentDetail:
    question = owned(db, user, question_id)
    return _build_detail(question, _latest_with_figures(db, question_id))


def _canonical_uuid(value: str, *, figure_index: int) -> str:
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise _issue(
            "invalid_figure_id",
            "配图 ID 必须是 UUID",
            figure_id=str(value),
            figure_index=figure_index,
        ) from exc


def _resolve_figures(
    db: Session,
    question: Question,
    revision: QuestionRevision | None,
    payload: QuestionDocumentUpdate,
    snapshot: dict[str, Any],
) -> tuple[dict[str, QuestionFigure], list[tuple[str, list[float]]], SourceAsset | None]:
    referenced = snapshot_figure_ids(snapshot)
    if len(referenced) > QUESTION_MAX_FIGURES:
        raise _issue("too_many_figures", f"每题最多包含 {QUESTION_MAX_FIGURES} 张配图")

    declarations: dict[str, Any] = {}
    for index, declaration in enumerate(payload.figures):
        stable_id = _canonical_uuid(declaration.id, figure_index=index)
        if stable_id in declarations:
            raise _issue(
                "duplicate_figure_declaration",
                "配图声明不能重复",
                figure_id=stable_id,
                figure_index=index,
            )
        if declaration.kind not in {"existing", "crop"}:
            raise _issue(
                "invalid_figure_source",
                "配图来源必须是 existing 或 crop",
                figure_id=stable_id,
                figure_index=index,
            )
        declarations[stable_id] = declaration

    declared = set(declarations)
    if referenced != declared:
        missing = sorted(referenced - declared)
        extra = sorted(declared - referenced)
        if missing:
            raise _issue("figure_not_declared", "内容中引用的配图未声明", figure_id=missing[0])
        raise _issue("unreferenced_figure", "配图声明未被内容引用", figure_id=extra[0])

    existing_rows = (
        db.query(QuestionFigure)
        .options(selectinload(QuestionFigure.figure_asset))
        .filter(QuestionFigure.question_id == question.id, QuestionFigure.stable_id.in_(declared))
        .all()
        if declared
        else []
    )
    existing = {figure.stable_id: figure for figure in existing_rows}
    globally_existing_ids = {
        stable_id
        for (stable_id,) in db.query(QuestionFigure.stable_id)
        .filter(QuestionFigure.stable_id.in_(declared))
        .all()
    } if declared else set()
    crops: list[tuple[str, list[float]]] = []
    for index, (stable_id, declaration) in enumerate(declarations.items()):
        if declaration.kind == "existing":
            if declaration.crop_bbox is not None or stable_id not in existing:
                raise _issue(
                    "unknown_existing_figure",
                    "配图不存在或不属于当前题目",
                    figure_id=stable_id,
                    figure_index=index,
                )
        else:
            if stable_id in globally_existing_ids:
                raise _issue(
                    "figure_id_already_exists",
                    "新裁剪不能复用已有配图 ID",
                    figure_id=stable_id,
                    figure_index=index,
                )
            try:
                relative_bbox = normalize_unit_bbox(declaration.crop_bbox)
            except ValueError as exc:
                raise _issue(
                    "invalid_crop_bbox",
                    str(exc),
                    figure_id=stable_id,
                    figure_index=index,
                ) from exc
            page_bbox = compose_bbox_to_page(revision.crop_bbox if revision else None, relative_bbox)
            if page_bbox is None:
                raise _issue("invalid_crop_bbox", "裁剪框无效", figure_id=stable_id)
            crops.append((stable_id, page_bbox))

    source_asset = revision.source_asset if revision else None
    if crops and source_asset is None:
        raise _issue("missing_question_source", "当前题目没有可用于裁图的原始图片")

    crop_entries = [
        (figure.stable_id, figure.source_asset_id, figure.source_crop_bbox)
        for figure in existing.values()
        if figure.stable_id in declared
    ]
    crop_entries.extend((stable_id, source_asset.id, bbox) for stable_id, bbox in crops)
    for index, (stable_id, source_id, bbox) in enumerate(crop_entries):
        for other_id, other_source_id, other_bbox in crop_entries[index + 1 :]:
            if source_id == other_source_id and _rectangles_overlap(bbox, other_bbox):
                raise _issue(
                    "crop_overlap",
                    "配图来源裁剪框不能重叠",
                    figure_id=stable_id,
                )
    return existing, crops, source_asset


def _prepare_crops(source_asset: SourceAsset, crops: list[tuple[str, list[float]]]) -> list[PreparedCrop]:
    source_path = resolve_upload_file_path(source_asset.normalized_path or source_asset.original_path)
    if not source_path:
        raise _issue("missing_question_source", "题目原始图片不存在")
    prepared: list[PreparedCrop] = []
    temp_paths: list[Path] = []
    try:
        with Image.open(source_path) as image:
            image.load()
            rgb_image = image.convert("RGB")
            for stable_id, bbox in crops:
                cropped = rgb_image.crop(pixel_crop_box(image, bbox))
                cropped.load()
                temp_path = settings.UPLOAD_DIR_PATH / f".tmp_question_figure_{uuid.uuid4().hex}.jpg"
                temp_paths.append(temp_path)
                temp_path.parent.mkdir(parents=True, exist_ok=True)
                cropped.save(temp_path, format="JPEG", quality=90)
                data = temp_path.read_bytes()
                if len(data) > QUESTION_MAX_FIGURE_BYTES:
                    raise _issue(
                        "figure_too_large",
                        f"单张配图不能超过 {QUESTION_MAX_FIGURE_BYTES} 字节",
                        figure_id=stable_id,
                    )
                prepared.append(
                    PreparedCrop(
                        stable_id=stable_id,
                        source_asset=source_asset,
                        source_bbox=bbox,
                        temp_path=temp_path,
                        digest=hashlib.sha256(data).hexdigest(),
                        size_bytes=len(data),
                        width=cropped.width,
                        height=cropped.height,
                    )
                )
    except Exception:
        for path in temp_paths:
            path.unlink(missing_ok=True)
        raise
    return prepared


def _validate_figure_sizes_and_aspect(
    snapshot: dict[str, Any], figures: dict[str, QuestionFigure], prepared: list[PreparedCrop]
) -> None:
    dimensions = {
        stable_id: (figure.figure_asset.width, figure.figure_asset.height, figure.figure_asset.size_bytes)
        for stable_id, figure in figures.items()
    }
    dimensions.update(
        {item.stable_id: (item.width, item.height, item.size_bytes) for item in prepared}
    )
    total = sum(int(values[2] or 0) for values in dimensions.values())
    if total > settings.QUESTION_MAX_TOTAL_FIGURE_BYTES:
        raise _issue("question_figure_bytes_exceeded", "题目配图累计体积超过上限")

    for section_name, section in snapshot["sections"].items():
        for block_index, block in enumerate(section["blocks"]):
            if block["kind"] != "image_area":
                continue
            for placement in block["placements"]:
                width, height, _ = dimensions[placement["figure_id"]]
                if not width or not height:
                    continue
                displayed_ratio = placement["width"] / (placement["height"] * block["height_ratio"])
                source_ratio = width / height
                if not math.isclose(displayed_ratio, source_ratio, rel_tol=0.02, abs_tol=0.02):
                    raise _issue(
                        "aspect_ratio_mismatch",
                        "配图摆放必须保持原图比例",
                        section=section_name,
                        block_id=block["id"],
                        block_index=block_index,
                        figure_id=placement["figure_id"],
                    )


def update_document(
    db: Session, user: User, question_id: int, payload: QuestionDocumentUpdate
) -> QuestionDocumentUpdateResponse:
    question = owned(db, user, question_id)
    revision = _latest_with_figures(db, question_id)
    current_revision_no = revision.rev_no if revision else 0
    if payload.expected_revision_no != current_revision_no:
        raise HTTPException(status_code=409, detail="版本冲突")
    if payload.schema_version != 2:
        raise _issue("unsupported_schema_version", "仅支持 schema_version 2")
    if payload.metadata.question_type is not None and payload.metadata.question_type not in QUESTION_TYPES:
        raise _issue("invalid_question_type", "非法题型", field="metadata.question_type")

    snapshot = _validate_snapshot({"schema_version": payload.schema_version, "sections": payload.sections})
    existing, crops, source_asset = _resolve_figures(db, question, revision, payload, snapshot)
    prepared = _prepare_crops(source_asset, crops) if source_asset else []
    promoted: list[Path] = []
    committed = False
    try:
        _validate_figure_sizes_and_aspect(snapshot, existing, prepared)
        projected = project_legacy_text(snapshot)
        tags = _tags(payload.metadata.knowledge_tags)
        current_detail = _build_detail(question, revision)
        declarations_are_existing = not prepared and set(existing) == {item.id for item in payload.figures}
        if (
            declarations_are_existing
            and current_detail.sections == snapshot["sections"]
            and [tag.model_dump() for tag in current_detail.knowledge_tags] == tags
            and current_detail.question_type == payload.metadata.question_type
            and current_detail.difficulty_level == payload.metadata.difficulty_level
        ):
            return QuestionDocumentUpdateResponse(
                revision_created=False,
                current_revision_no=current_revision_no,
                question=current_detail,
            )

        resolved = dict(existing)
        for item in prepared:
            asset = db.query(SourceAsset).filter(SourceAsset.sha256 == item.digest).first()
            if asset is None:
                final_name = f"{uuid.uuid4().hex}_figure.jpg"
                final_path = settings.UPLOAD_DIR_PATH / final_name
                item.temp_path.replace(final_path)
                promoted.append(final_path)
                asset = SourceAsset(
                    user_id=question.user_id,
                    kind="figure",
                    original_path=final_name,
                    normalized_path=None,
                    mime="image/jpeg",
                    size_bytes=item.size_bytes,
                    width=item.width,
                    height=item.height,
                    sha256=item.digest,
                )
                db.add(asset)
                db.flush()
            else:
                item.temp_path.unlink(missing_ok=True)
            figure = QuestionFigure(
                stable_id=item.stable_id,
                question_id=question.id,
                source_asset_id=item.source_asset.id,
                figure_asset_id=asset.id,
                source_crop_bbox=item.source_bbox,
            )
            db.add(figure)
            db.flush()
            resolved[item.stable_id] = figure

        values = {
            "text": projected["content"],
            "answer": projected["answer"],
            "analysis": projected["analysis"],
            "knowledge_tags": tags,
            "question_type": payload.metadata.question_type,
            "difficulty_level": payload.metadata.difficulty_level,
            "difficulty_label": question.difficulty_label,
        }
        question.content = values["text"]
        question.answer = values["answer"]
        question.analysis = values["analysis"]
        question.knowledge_tags = tags
        question.question_type = values["question_type"]
        question.difficulty_level = values["difficulty_level"]
        question.section_snapshot = snapshot
        question.metadata_generation = (question.metadata_generation or 0) + 1
        referenced_ids = sorted(snapshot_figure_ids(snapshot))
        legacy_figure = resolved[referenced_ids[0]] if len(referenced_ids) == 1 else None
        question.figure_image = (
            legacy_figure.figure_asset.normalized_path or legacy_figure.figure_asset.original_path
            if legacy_figure
            else None
        )
        question.figure_crop_bbox = legacy_figure.source_crop_bbox if legacy_figure else None

        new_revision = QuestionRevision(
            question=question,
            rev_no=current_revision_no + 1,
            content=values,
            section_snapshot=snapshot,
            crop_bbox=revision.crop_bbox if revision else None,
            source_asset_id=revision.source_asset_id if revision else None,
            figure_asset_id=legacy_figure.figure_asset_id if legacy_figure else None,
            change_reason="document_edit",
        )
        db.add(new_revision)
        db.flush()
        for stable_id in sorted(snapshot_figure_ids(snapshot)):
            db.add(
                QuestionRevisionFigure(
                    question_id=question.id,
                    question_revision_id=new_revision.id,
                    question_figure_id=resolved[stable_id].id,
                )
            )
        db.commit()
        committed = True
        db.refresh(question)
        db.refresh(new_revision)
        detail = _build_detail(question, new_revision)
        return QuestionDocumentUpdateResponse(
            revision_created=True,
            current_revision_no=new_revision.rev_no,
            question=detail,
        )
    except IntegrityError as exc:
        db.rollback()
        if not committed:
            for path in promoted:
                path.unlink(missing_ok=True)
        if "rev_no" in str(exc).lower():
            raise HTTPException(status_code=409, detail="版本冲突") from exc
        raise
    except Exception:
        db.rollback()
        if not committed:
            for path in promoted:
                path.unlink(missing_ok=True)
        raise
    finally:
        for item in prepared:
            item.temp_path.unlink(missing_ok=True)


def get_figure_file(db: Session, user: User, question_id: int, figure_id: str) -> FigureFile:
    question = owned(db, user, question_id)
    try:
        stable_id = str(uuid.UUID(figure_id))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(status_code=404, detail="资源不存在")
    figure = (
        db.query(QuestionFigure)
        .filter(QuestionFigure.question_id == question.id, QuestionFigure.stable_id == stable_id)
        .first()
    )
    if not figure or not figure.figure_asset:
        raise HTTPException(status_code=404, detail="资源不存在")
    path = resolve_upload_file_path(
        figure.figure_asset.normalized_path or figure.figure_asset.original_path
    )
    if not path:
        raise HTTPException(status_code=404, detail="资源不存在")
    return FigureFile(path=path, mime=figure.figure_asset.mime)
