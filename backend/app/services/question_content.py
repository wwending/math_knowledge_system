from __future__ import annotations

from copy import deepcopy
import math
from typing import Any, Mapping, Optional, Sequence
from uuid import NAMESPACE_URL, uuid5

from app.services.question_identifiers import canonical_uuid

SCHEMA_VERSION = 2
SECTION_NAMES = ("stem", "answer", "analysis")
BLOCK_KINDS = {"text", "image_area"}


class ContentSnapshotError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "invalid_document",
        section: str | None = None,
        block_id: str | None = None,
        block_index: int | None = None,
        figure_id: str | None = None,
        placement_index: int | None = None,
        field: str | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.section = section
        self.block_id = block_id
        self.block_index = block_index
        self.figure_id = figure_id
        self.placement_index = placement_index
        self.field = field


def _stable_uuid(seed: str, *parts: object) -> str:
    value = ":".join(["math-knowledge-system", seed, *(str(part) for part in parts)])
    return str(uuid5(NAMESPACE_URL, value))


def _optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = value if isinstance(value, str) else str(value)
    text = text.strip()
    return text or None


def _coordinate(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContentSnapshotError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ContentSnapshotError(f"{field} must be finite")
    if number < 0 or number > 1:
        raise ContentSnapshotError(f"{field} must be between 0 and 1")
    return number


def _canonical_uuid(value: Any, field: str) -> str:
    try:
        return canonical_uuid(value)
    except (TypeError, ValueError, AttributeError) as exc:
        raise ContentSnapshotError(f"{field} must be a UUID") from exc


def _text_block(seed: str, section: str, markdown: str) -> dict[str, Any]:
    return {
        "id": _stable_uuid(seed, section, "text", 0),
        "kind": "text",
        "markdown": markdown,
    }


def _image_area(
    seed: str,
    figure_id: str,
    figure_aspect_ratio: Optional[float],
) -> dict[str, Any]:
    height_ratio = float(figure_aspect_ratio or 1.0)
    if height_ratio <= 0:
        height_ratio = 1.0
    return {
        "id": _stable_uuid(seed, "stem", "image_area", 0),
        "kind": "image_area",
        "height_ratio": height_ratio,
        "placements": [
            {
                "figure_id": _canonical_uuid(figure_id, "figure_id"),
                "x": 0.0,
                "y": 0.0,
                "width": 1.0,
                "height": 1.0,
            }
        ],
    }


def legacy_figure_stable_id(question_id: int) -> str:
    return _stable_uuid("question", question_id, "legacy_figure")


def draft_figure_stable_id(question_id: int, index: int, total: int) -> str:
    if total == 1:
        return legacy_figure_stable_id(question_id)
    return _stable_uuid("question", question_id, "draft_figure", index)


def build_draft_v2_snapshot(
    *,
    content: Any,
    seed: str,
    figures: Sequence[Mapping[str, Any]],
    canvas_width: int,
) -> dict[str, Any]:
    """Build the initial natural-size figure layout for a saved Draft."""

    if canvas_width <= 0:
        raise ContentSnapshotError("canvas_width must be positive")

    placements_px: list[dict[str, Any]] = []
    left = 0
    top = 0
    row_height = 0
    for index, figure in enumerate(figures):
        width = int(figure.get("width") or 0)
        height = int(figure.get("height") or 0)
        if width <= 0 or height <= 0 or width > canvas_width:
            raise ContentSnapshotError("figure dimensions must fit the Draft canvas")
        if left > 0 and left + width > canvas_width:
            top += row_height
            left = 0
            row_height = 0
        placements_px.append(
            {
                "figure_id": _canonical_uuid(figure.get("figure_id"), f"figures[{index}].figure_id"),
                "left": left,
                "top": top,
                "width": width,
                "height": height,
            }
        )
        left += width
        row_height = max(row_height, height)

    canvas_height = top + row_height if placements_px else 0
    snapshot = build_legacy_v2_snapshot(content=content, seed=seed)
    if not placements_px:
        return snapshot

    placements = [
        {
            "figure_id": item["figure_id"],
            "x": item["left"] / canvas_width,
            "y": item["top"] / canvas_height,
            "width": item["width"] / canvas_width,
            "height": item["height"] / canvas_height,
        }
        for item in placements_px
    ]
    snapshot["sections"]["stem"]["blocks"].append(
        {
            "id": _stable_uuid(seed, "stem", "image_area", 0),
            "kind": "image_area",
            "height_ratio": canvas_height / canvas_width,
            "placements": placements,
        }
    )
    snapshot.pop("compatibility_state", None)
    return normalize_v2_snapshot(snapshot)


def adapt_section_snapshot(
    *,
    section_snapshot: Any,
    content: Any,
    answer: Any,
    analysis: Any,
    seed: str,
    legacy_figure_id: Optional[str] = None,
    figure_aspect_ratio: Optional[float] = None,
) -> dict[str, Any]:
    if isinstance(section_snapshot, Mapping):
        return clone_snapshot(section_snapshot)
    return build_legacy_v2_snapshot(
        content=content,
        answer=answer,
        analysis=analysis,
        seed=seed,
        figure_id=legacy_figure_id,
        figure_aspect_ratio=figure_aspect_ratio,
    )


def build_legacy_v2_snapshot(
    *,
    content: Any,
    answer: Any = None,
    analysis: Any = None,
    seed: str,
    figure_id: Optional[str] = None,
    figure_aspect_ratio: Optional[float] = None,
) -> dict[str, Any]:
    """Project flat legacy fields to a deterministic schema-v2 snapshot.

    Invalid historical rows with neither stem text nor a figure remain readable as
    an explicit compatibility state. New user writes must validate without
    ``allow_incomplete_stem`` and therefore cannot create this state.
    """

    stem_text = _optional_text(content)
    answer_text = _optional_text(answer)
    analysis_text = _optional_text(analysis)

    stem_blocks: list[dict[str, Any]] = []
    if stem_text:
        stem_blocks.append(_text_block(seed, "stem", stem_text))
    if figure_id:
        stem_blocks.append(_image_area(seed, figure_id, figure_aspect_ratio))

    snapshot: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "sections": {
            "stem": {"blocks": stem_blocks},
            "answer": {
                "blocks": [_text_block(seed, "answer", answer_text)] if answer_text else []
            },
            "analysis": {
                "blocks": [_text_block(seed, "analysis", analysis_text)] if analysis_text else []
            },
        },
    }
    if not stem_blocks:
        snapshot["compatibility_state"] = "incomplete_stem"
    return normalize_v2_snapshot(snapshot, allow_incomplete_stem=True)


def normalize_v2_snapshot(
    snapshot: Mapping[str, Any],
    *,
    allow_incomplete_stem: bool = False,
) -> dict[str, Any]:
    if not isinstance(snapshot, Mapping):
        raise ContentSnapshotError("snapshot must be an object")
    if snapshot.get("schema_version") != SCHEMA_VERSION:
        raise ContentSnapshotError("unsupported schema_version")

    sections = snapshot.get("sections")
    if not isinstance(sections, Mapping) or set(sections) != set(SECTION_NAMES):
        raise ContentSnapshotError("sections must contain stem, answer, and analysis")

    seen_block_ids: set[str] = set()
    placed_figures: set[str] = set()
    normalized_sections: dict[str, Any] = {}
    for section_name in SECTION_NAMES:
        section = sections[section_name]
        if not isinstance(section, Mapping) or set(section) != {"blocks"}:
            raise ContentSnapshotError(f"{section_name} must contain only blocks")
        blocks = section.get("blocks")
        if not isinstance(blocks, list):
            raise ContentSnapshotError(f"{section_name}.blocks must be an array")

        normalized_blocks: list[dict[str, Any]] = []
        for block_index, block in enumerate(blocks):
            if not isinstance(block, Mapping):
                raise ContentSnapshotError(f"{section_name}.blocks[{block_index}] must be an object")
            block_id = _canonical_uuid(block.get("id"), "block.id")
            if block_id in seen_block_ids:
                raise ContentSnapshotError("block ids must be unique")
            seen_block_ids.add(block_id)
            kind = block.get("kind")
            if kind not in BLOCK_KINDS:
                raise ContentSnapshotError("unsupported block kind")

            if kind == "text":
                if set(block) != {"id", "kind", "markdown"}:
                    raise ContentSnapshotError("text block has unknown fields")
                markdown = _optional_text(block.get("markdown"))
                if not markdown:
                    raise ContentSnapshotError("text block markdown cannot be empty")
                normalized_blocks.append(
                    {"id": block_id, "kind": "text", "markdown": markdown}
                )
                continue

            if set(block) != {"id", "kind", "height_ratio", "placements"}:
                raise ContentSnapshotError("image area has unknown fields")
            height_ratio = block.get("height_ratio")
            if isinstance(height_ratio, bool) or not isinstance(height_ratio, (int, float)):
                raise ContentSnapshotError("height_ratio must be a number")
            height_ratio = float(height_ratio)
            if not math.isfinite(height_ratio):
                raise ContentSnapshotError("height_ratio must be finite")
            if height_ratio <= 0:
                raise ContentSnapshotError("height_ratio must be positive")
            placements = block.get("placements")
            if not isinstance(placements, list):
                raise ContentSnapshotError("placements must be an array")

            normalized_placements: list[dict[str, Any]] = []
            seen_figures: set[str] = set()
            for placement_index, placement in enumerate(placements):
                if not isinstance(placement, Mapping) or set(placement) != {
                    "figure_id",
                    "x",
                    "y",
                    "width",
                    "height",
                }:
                    raise ContentSnapshotError(
                        f"placements[{placement_index}] has invalid fields"
                    )
                figure_id = _canonical_uuid(placement.get("figure_id"), "figure_id")
                if figure_id in seen_figures or figure_id in placed_figures:
                    raise ContentSnapshotError(
                        "a figure can appear only once in a question document",
                        code="duplicate_figure_placement",
                        section=section_name,
                        block_id=block_id,
                        block_index=block_index,
                        figure_id=figure_id,
                        placement_index=placement_index,
                        field="figure_id",
                    )
                seen_figures.add(figure_id)
                placed_figures.add(figure_id)
                x = _coordinate(placement.get("x"), "x")
                y = _coordinate(placement.get("y"), "y")
                width = _coordinate(placement.get("width"), "width")
                height = _coordinate(placement.get("height"), "height")
                if width <= 0 or height <= 0 or x + width > 1 or y + height > 1:
                    raise ContentSnapshotError("placement must fit inside the image area")
                normalized_placements.append(
                    {
                        "figure_id": figure_id,
                        "x": x,
                        "y": y,
                        "width": width,
                        "height": height,
                    }
                )
            normalized_blocks.append(
                {
                    "id": block_id,
                    "kind": "image_area",
                    "height_ratio": height_ratio,
                    "placements": normalized_placements,
                }
            )

        normalized_sections[section_name] = {"blocks": normalized_blocks}

    stem_blocks = normalized_sections["stem"]["blocks"]
    has_stem_content = any(
        block["kind"] == "text" or block["placements"] for block in stem_blocks
    )
    compatibility_state = snapshot.get("compatibility_state")
    if not has_stem_content:
        if not allow_incomplete_stem or compatibility_state != "incomplete_stem":
            raise ContentSnapshotError("stem must contain text or a placed figure")
    elif compatibility_state is not None:
        raise ContentSnapshotError("compatibility_state is valid only for an incomplete stem")

    normalized: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "sections": normalized_sections,
    }
    if compatibility_state is not None:
        normalized["compatibility_state"] = compatibility_state
    return normalized


def replace_legacy_text(
    snapshot: Mapping[str, Any],
    *,
    content: Any,
    answer: Any,
    analysis: Any,
    seed: str,
) -> dict[str, Any]:
    normalized = clone_snapshot(snapshot)
    replacements = {
        "stem": _optional_text(content),
        "answer": _optional_text(answer),
        "analysis": _optional_text(analysis),
    }
    for section_name, markdown in replacements.items():
        blocks = normalized["sections"][section_name]["blocks"]
        first_text_index = next(
            (index for index, block in enumerate(blocks) if block["kind"] == "text"),
            None,
        )
        first_text_id = (
            blocks[first_text_index]["id"]
            if first_text_index is not None
            else _stable_uuid(seed, section_name, "text", 0)
        )
        image_areas = [block for block in blocks if block["kind"] == "image_area"]
        if markdown:
            insert_at = first_text_index if first_text_index is not None else 0
            image_areas.insert(
                min(insert_at, len(image_areas)),
                {"id": first_text_id, "kind": "text", "markdown": markdown},
            )
        normalized["sections"][section_name]["blocks"] = image_areas

    normalized.pop("compatibility_state", None)
    has_stem_content = any(
        block["kind"] == "text" or block["placements"]
        for block in normalized["sections"]["stem"]["blocks"]
    )
    if not has_stem_content:
        normalized["compatibility_state"] = "incomplete_stem"
    return normalize_v2_snapshot(normalized, allow_incomplete_stem=not has_stem_content)


def project_legacy_text(snapshot: Mapping[str, Any]) -> dict[str, Optional[str]]:
    normalized = normalize_v2_snapshot(
        snapshot,
        allow_incomplete_stem=snapshot.get("compatibility_state") == "incomplete_stem",
    )

    def section_text(section_name: str) -> Optional[str]:
        values = [
            block["markdown"]
            for block in normalized["sections"][section_name]["blocks"]
            if block["kind"] == "text"
        ]
        return "\n\n".join(values) or None

    return {
        "content": section_text("stem"),
        "answer": section_text("answer"),
        "analysis": section_text("analysis"),
    }


def snapshot_figure_ids(snapshot: Mapping[str, Any]) -> set[str]:
    normalized = normalize_v2_snapshot(
        snapshot,
        allow_incomplete_stem=snapshot.get("compatibility_state") == "incomplete_stem",
    )
    return {
        placement["figure_id"]
        for section in normalized["sections"].values()
        for block in section["blocks"]
        if block["kind"] == "image_area"
        for placement in block["placements"]
    }


def clone_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return deepcopy(
        normalize_v2_snapshot(
            snapshot,
            allow_incomplete_stem=snapshot.get("compatibility_state") == "incomplete_stem",
        )
    )
