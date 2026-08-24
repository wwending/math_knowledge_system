"""Figure-region layout analysis for question crops (#58).

Detects figure regions (geometry plots, function graphs, charts) inside a
single-question crop image using RapidLayout's DocLayout-YOLO model on
ONNXRuntime CPU. Every failure mode (disabled, missing model, download
failure, engine error, timeout) degrades to an unsuccessful LayoutResult so
the draft pipeline can fall back to the pre-#58 no-figure flow instead of
blocking question entry.

The heavy dependencies (rapid_layout / onnxruntime) are imported lazily
inside engine construction, mirroring the rapidocr provider pattern: the app
boots and the test suite runs even when they are not installed.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from pathlib import Path

import requests
from loguru import logger
from PIL import Image, ImageDraw

from app.core.config import settings

# Model zoo entry (RapidLayout v1.2.0 release assets on ModelScope). Auto-download
# is only wired for models listed here; any other LAYOUT_MODEL_TYPE requires an
# explicit LAYOUT_MODEL_PATH pointing at a locally available .onnx file.
MODEL_SPECS: dict[str, tuple[str, str]] = {
    "doclayout_docstructbench": (
        "https://www.modelscope.cn/models/RapidAI/RapidLayout/resolve/v1.2.0/onnx/"
        "doclayout/doclayout_yolo_docstructbench_imgsz1024.onnx",
        "3b452baef10ecabd615491bc82cc4d49475fbc2cd7a8e535044f2c6bb28fb9fe",
    ),
}
DOWNLOAD_CONNECT_TIMEOUT_SECONDS = 10
DOWNLOAD_READ_TIMEOUT_SECONDS = 120


class LayoutModelUnavailable(RuntimeError):
    """Raised internally when the detection model cannot be provisioned."""

    def __init__(self, error_type: str, message: str):
        super().__init__(message)
        self.error_type = error_type


@dataclass
class FigureBox:
    """A detected figure region; bbox is [x, y, w, h] normalized to [0, 1]."""

    bbox: list[float]
    label: str
    score: float


@dataclass
class LayoutResult:
    success: bool
    boxes: list[FigureBox] = field(default_factory=list)
    latency_ms: int = 0
    # disabled | model_missing | download_failed | engine_error | timeout | invalid_image
    error_type: str | None = None
    detail: str | None = None


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class LayoutService:
    """detect() never raises: every problem becomes a degraded LayoutResult."""

    def __init__(self, engine_factory=None):
        # engine_factory lets tests inject a fake engine; production builds one
        # lazily via _build_engine after the model file is in place.
        self._engine_factory = engine_factory
        self._engine = None
        # Single-worker pool used as a timeout guard: on timeout the future is
        # abandoned (a running ONNX call cannot be killed from Python); the
        # thread finishes in the background and later calls queue behind it.
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="layout-detect")

    # -- public API ---------------------------------------------------------

    def detect(self, image_path: str | Path) -> LayoutResult:
        started_at = time.perf_counter()
        if not settings.LAYOUT_ENABLED:
            return LayoutResult(success=False, error_type="disabled")

        def elapsed_ms() -> int:
            return int((time.perf_counter() - started_at) * 1000)

        try:
            engine = self._get_engine()
            raw = self._executor.submit(engine, str(image_path)).result(
                timeout=settings.LAYOUT_TIMEOUT_SECONDS
            )
            width, height = _image_size(image_path)
            boxes = _normalize_boxes(raw, width, height)
        except FutureTimeoutError:
            logger.warning(
                "[LayoutDetect] timed out after {}s path={}", settings.LAYOUT_TIMEOUT_SECONDS, image_path
            )
            return LayoutResult(success=False, latency_ms=elapsed_ms(), error_type="timeout")
        except LayoutModelUnavailable as exc:
            logger.warning("[LayoutDetect] model unavailable: {}", exc)
            return LayoutResult(
                success=False, latency_ms=elapsed_ms(), error_type=exc.error_type, detail=str(exc)
            )
        except Exception as exc:  # noqa: BLE001 - degrade, never break the flow
            logger.exception("[LayoutDetect] unexpected engine failure: {}", exc)
            return LayoutResult(
                success=False, latency_ms=elapsed_ms(), error_type="engine_error", detail=str(exc)
            )

        result = LayoutResult(success=True, boxes=boxes, latency_ms=elapsed_ms())
        logger.info(
            "[LayoutDetect] ok path={} boxes={} filtered_latency_ms={}",
            image_path,
            len(boxes),
            result.latency_ms,
        )
        return result

    def ensure_model(self) -> Path:
        """Return a usable model file path, downloading it on first use."""
        model_path = _resolve_model_path()
        spec = MODEL_SPECS.get(settings.LAYOUT_MODEL_TYPE.strip().lower())
        if model_path.exists():
            # Only checksum-guard files this service itself manages; an explicit
            # LAYOUT_MODEL_PATH override is trusted as-is.
            if spec and model_path == _canonical_model_path():
                expected_sha = spec[1]
                if _sha256_of(model_path) != expected_sha:
                    logger.warning("[LayoutDetect] cached model failed SHA256 check; re-downloading")
                    model_path.unlink(missing_ok=True)
                else:
                    return model_path
            else:
                return model_path

        if spec is None:
            raise LayoutModelUnavailable(
                "model_missing",
                f"No local model for LAYOUT_MODEL_TYPE={settings.LAYOUT_MODEL_TYPE!r}; "
                "set LAYOUT_MODEL_PATH to an existing .onnx file.",
            )

        url, expected_sha = spec
        target_dir = model_path.parent
        target_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = target_dir / f".{model_path.name}.{uuid.uuid4().hex}.tmp"
        try:
            with requests.get(
                url,
                stream=True,
                timeout=(DOWNLOAD_CONNECT_TIMEOUT_SECONDS, DOWNLOAD_READ_TIMEOUT_SECONDS),
            ) as response:
                response.raise_for_status()
                with tmp_path.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        handle.write(chunk)
            if _sha256_of(tmp_path) != expected_sha:
                raise LayoutModelUnavailable(
                    "download_failed", f"Downloaded model failed SHA256 check: {url}"
                )
            tmp_path.replace(model_path)
        except LayoutModelUnavailable:
            tmp_path.unlink(missing_ok=True)
            raise
        except Exception as exc:  # noqa: BLE001 - network/IO failures degrade
            tmp_path.unlink(missing_ok=True)
            raise LayoutModelUnavailable("download_failed", f"Model download failed: {exc}") from exc
        logger.info("[LayoutDetect] model ready at {}", model_path)
        return model_path

    # -- internals ----------------------------------------------------------

    def _get_engine(self):
        if self._engine is None:
            if self._engine_factory is not None:
                self._engine = self._engine_factory()
            else:
                self._engine = self._build_engine(self.ensure_model())
        return self._engine

    def _build_engine(self, model_path: Path):
        from rapid_layout import RapidLayout  # lazy heavy import (#58 degradation contract)

        # NOTE: rapid-layout's kwarg names are conf_thresh/iou_thresh (its
        # config normalizer silently drops unknown keys).
        return RapidLayout(
            model_type=settings.LAYOUT_MODEL_TYPE,
            conf_thresh=settings.LAYOUT_CONF_THRESHOLD,
            iou_thresh=0.5,
            engine_type="onnxruntime",
            model_dir_or_path=str(model_path),
        )


def _resolve_model_path() -> Path:
    override = settings.LAYOUT_MODEL_PATH.strip()
    if override:
        return Path(override).expanduser()
    return _canonical_model_path()


def _canonical_model_path() -> Path:
    model_type = settings.LAYOUT_MODEL_TYPE.strip().lower()
    return settings.LAYOUT_MODEL_DIR_PATH / f"{model_type}.onnx"


def _image_size(image_path: str | Path) -> tuple[int, int]:
    with Image.open(image_path) as img:
        return img.width, img.height


def _normalize_boxes(raw, width: int, height: int) -> list[FigureBox]:
    """Convert engine output (pixel xyxy + labels + scores) to normalized xywh.

    Keeps only configured figure labels, drops degenerate/too-small regions,
    clamps to image bounds, and orders top-to-bottom then left-to-right.
    """
    if raw is None:
        return []
    pixel_boxes = getattr(raw, "boxes", None)
    class_names = getattr(raw, "class_names", None)
    scores = getattr(raw, "scores", None)
    if pixel_boxes is None or class_names is None:
        return []

    labels_set = settings.LAYOUT_FIGURE_LABELS_SET
    min_area_ratio = max(float(settings.LAYOUT_MIN_AREA_RATIO), 0.0)
    figure_boxes: list[FigureBox] = []
    for index, pixel_box in enumerate(pixel_boxes):
        label = str(class_names[index]).strip().lower() if index < len(class_names) else ""
        if labels_set and label not in labels_set:
            continue
        try:
            x1, y1, x2, y2 = (float(v) for v in list(pixel_box)[:4])
        except (TypeError, ValueError):
            continue
        x1, x2 = sorted((min(max(x1, 0.0), float(width)), min(max(x2, 0.0), float(width))))
        y1, y2 = sorted((min(max(y1, 0.0), float(height)), min(max(y2, 0.0), float(height))))
        box_w, box_h = x2 - x1, y2 - y1
        if box_w <= 0 or box_h <= 0:
            continue
        if height <= 0 or width <= 0:
            continue
        if (box_w * box_h) / float(width * height) < min_area_ratio:
            continue
        try:
            score = float(scores[index]) if index < len(scores) else 0.0
        except (TypeError, ValueError):
            score = 0.0
        figure_boxes.append(
            FigureBox(
                bbox=[x1 / width, y1 / height, box_w / width, box_h / height],
                label=label,
                score=score,
            )
        )
    figure_boxes.sort(key=lambda box: (box.bbox[1], box.bbox[0]))
    return figure_boxes


def write_masked_image(image_path: str | Path, boxes: list[FigureBox]) -> Path | None:
    """White-out figure regions so OCR only sees text areas.

    Returns None when masking cannot be produced; callers must treat that as
    "send the original image" rather than failing recognition.
    """
    if not boxes:
        return None
    try:
        with Image.open(image_path) as img:
            rgb = img.convert("RGB")
            draw = ImageDraw.Draw(rgb)
            for box in boxes:
                x, y, w, h = box.bbox
                rectangle = (
                    round(min(max(x, 0.0), 1.0) * rgb.width),
                    round(min(max(y, 0.0), 1.0) * rgb.height),
                    round(min(max(x + w, 0.0), 1.0) * rgb.width),
                    round(min(max(y + h, 0.0), 1.0) * rgb.height),
                )
                if rectangle[2] <= rectangle[0] or rectangle[3] <= rectangle[1]:
                    continue
                draw.rectangle(rectangle, fill=(255, 255, 255))
            # UPLOAD_DIR stays private (#44); masked temps are deleted right
            # after the OCR call by the caller.
            out_path = settings.UPLOAD_DIR_PATH / f"tmp_masked_{uuid.uuid4().hex}.jpg"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            rgb.save(out_path, format="JPEG", quality=92)
            return out_path
    except Exception as exc:  # noqa: BLE001 - masking is best-effort
        logger.warning("[LayoutDetect] masking failed, falling back to original image: {}", exc)
        return None


def remove_quiet(path: str | Path | None) -> None:
    if not path:
        return
    try:
        Path(path).unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("[LayoutDetect] failed to remove temp file {}: {}", path, exc)


layout_service = LayoutService()
