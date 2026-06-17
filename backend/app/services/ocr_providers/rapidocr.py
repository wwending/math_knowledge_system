from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from app.services.ocr_providers.base import OCRResult


@dataclass
class RapidOcrParsedResult:
    text: str
    boxes: list[Any] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)
    raw_response_summary: dict[str, Any] = field(default_factory=dict)


def _is_text_sequence(value: Any) -> bool:
    return isinstance(value, (list, tuple)) and all(isinstance(item, str) for item in value)


def _append_line(lines: list[str], boxes: list[Any], scores: list[float], text: Any, box: Any = None, score: Any = None) -> None:
    clean_text = str(text or "").strip()
    if not clean_text:
        return
    lines.append(clean_text)
    if box is not None:
        boxes.append(box)
    if score is not None:
        try:
            scores.append(float(score))
        except (TypeError, ValueError):
            pass


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    try:
        return list(value)
    except TypeError:
        return []


def _as_float_list(value: Any) -> list[float]:
    items = _as_list(value)
    scores: list[float] = []
    for item in items:
        try:
            scores.append(float(item))
        except (TypeError, ValueError):
            pass
    return scores


def _summary(line_count: int, boxes: list[Any], scores: list[float], shape: str) -> dict[str, Any]:
    return {
        "provider": "rapidocr",
        "success": True,
        "shape": shape,
        "line_count": line_count,
        "box_count": len(boxes),
        "scores": scores,
    }


def _unsupported_result_error(result: Any) -> ValueError:
    visible_attrs = [name for name in dir(result) if not name.startswith("__")][:20]
    preview = repr(result)[:500]
    return ValueError(
        "Unsupported RapidOCR result format: "
        f"type={type(result).__name__}; attrs={visible_attrs}; repr={preview}"
    )


def _parse_dict_item(item: dict[str, Any], lines: list[str], boxes: list[Any], scores: list[float]) -> None:
    text = item.get("text", item.get("txt", item.get("words", "")))
    _append_line(lines, boxes, scores, text, item.get("box"), item.get("score"))


def _parse_line_sequence(result: Any, shape: str) -> RapidOcrParsedResult | None:
    lines: list[str] = []
    boxes: list[Any] = []
    scores: list[float] = []
    parsed_any = False
    for item in result:
        if isinstance(item, dict):
            _parse_dict_item(item, lines, boxes, scores)
            parsed_any = True
            continue
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            box = item[0]
            text = item[1]
            score = item[2] if len(item) >= 3 else None
            _append_line(lines, boxes, scores, text, box, score)
            parsed_any = True

    if not parsed_any:
        return None

    return RapidOcrParsedResult(
        text="\n".join(lines),
        boxes=boxes,
        scores=scores,
        raw_response_summary=_summary(len(lines), boxes, scores, shape),
    )


def parse_rapidocr_result(result: Any) -> RapidOcrParsedResult:
    if result is None:
        return RapidOcrParsedResult(text="", raw_response_summary=_summary(0, [], [], "none"))

    txts = getattr(result, "txts", None)
    if txts is None:
        txts = getattr(result, "texts", None)
    if txts is not None:
        if not _is_text_sequence(txts):
            raise ValueError("Unsupported RapidOCR result format: txts/texts is not a text list")
        lines = [item.strip() for item in txts if item.strip()]
        boxes = _as_list(getattr(result, "boxes", None)) if lines else []
        scores = _as_float_list(getattr(result, "scores", None)) if lines else []
        return RapidOcrParsedResult(
            text="\n".join(lines),
            boxes=boxes,
            scores=scores,
            raw_response_summary=_summary(len(lines), boxes, scores, "object_attrs"),
        )

    for method_name in ("to_dict", "model_dump", "to_json"):
        method = getattr(result, method_name, None)
        if not callable(method):
            continue
        converted = method()
        if isinstance(converted, dict):
            for key in ("txts", "texts"):
                converted_txts = converted.get(key)
                if converted_txts is not None and _is_text_sequence(converted_txts):
                    lines = [item.strip() for item in converted_txts if item.strip()]
                    boxes = _as_list(converted.get("boxes")) if lines else []
                    scores = _as_float_list(converted.get("scores")) if lines else []
                    return RapidOcrParsedResult(
                        text="\n".join(lines),
                        boxes=boxes,
                        scores=scores,
                        raw_response_summary=_summary(len(lines), boxes, scores, method_name),
                    )
        if isinstance(converted, (list, tuple)):
            parsed = _parse_line_sequence(converted, method_name)
            if parsed is not None:
                return parsed

    if isinstance(result, (list, tuple)):
        if not result:
            return RapidOcrParsedResult(text="", raw_response_summary=_summary(0, [], [], "empty_sequence"))

        if len(result) >= 3 and _is_text_sequence(result[1]):
            lines = [item.strip() for item in result[1] if item.strip()]
            boxes = _as_list(result[0]) if lines else []
            scores = _as_float_list(result[2]) if lines else []
            return RapidOcrParsedResult(
                text="\n".join(lines),
                boxes=boxes,
                scores=scores,
                raw_response_summary=_summary(len(lines), boxes, scores, "tuple_boxes_txts_scores"),
            )

        parsed = _parse_line_sequence(result, "line_sequence")
        if parsed is not None:
            return parsed

    raise _unsupported_result_error(result)


class RapidOcrProvider:
    provider_name = "rapidocr"

    def __init__(self, engine: Any | None = None):
        self._engine = engine

    @property
    def endpoint(self) -> str | None:
        return "local"

    def _get_engine(self) -> Any:
        if self._engine is None:
            try:
                from rapidocr import RapidOCR
            except ImportError as exc:
                raise RuntimeError("RapidOCR is not installed. Install it with: pip install rapidocr") from exc
            self._engine = RapidOCR()
        return self._engine

    def recognize(self, image_path: str) -> OCRResult:
        started_at = time.time()
        engine = self._get_engine()
        try:
            raw_result = engine.ocr(image_path) if hasattr(engine, "ocr") else engine(image_path)
            parsed = parse_rapidocr_result(raw_result)
        except ValueError as exc:
            return OCRResult(
                text="",
                provider=self.provider_name,
                raw_response_summary={"provider": self.provider_name, "success": False},
                latency_ms=int((time.time() - started_at) * 1000),
                error="RapidOCR returned an unsupported result format",
                error_type="invalid_response",
                detail=str(exc),
            )

        return OCRResult(
            text=parsed.text,
            provider=self.provider_name,
            confidence=None,
            boxes=parsed.boxes,
            raw_response_summary=parsed.raw_response_summary,
            latency_ms=int((time.time() - started_at) * 1000),
        )
