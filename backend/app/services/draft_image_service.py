from __future__ import annotations

import math
import uuid
from pathlib import Path
from typing import Any

from PIL import Image

from app.core.config import settings

MIN_DRAFT_CROP_AREA_RATIO = 0.0025


def normalize_unit_bbox(value: Any) -> list[float] | dict[str, Any]:
    if value is None or value == {}:
        return {}
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("crop_bbox must be [x, y, width, height] normalized to [0, 1]")
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in value):
        raise ValueError("crop_bbox values must be finite numbers")
    values = [float(item) for item in value]
    if not all(math.isfinite(item) for item in values):
        raise ValueError("crop_bbox values must be finite numbers")
    x, y, width, height = values
    if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > 1 or y + height > 1:
        raise ValueError("crop_bbox must describe a positive region inside the image")
    return values


def normalize_draft_bbox(value: Any) -> list[float] | dict[str, Any]:
    """Normalize a Draft crop bbox, preserving the legacy {} full-image marker."""
    normalized = normalize_unit_bbox(value)
    if normalized != {} and normalized[2] * normalized[3] < MIN_DRAFT_CROP_AREA_RATIO:
        raise ValueError(
            f"crop_bbox area must be at least {MIN_DRAFT_CROP_AREA_RATIO:.4f} of the image"
        )
    return normalized


def is_full_image_bbox(value: Any) -> bool:
    return value is None or value == {}


def normalized_bbox_pixel_box(
    image: Image.Image, crop_bbox: Any
) -> tuple[int, int, int, int]:
    """Convert a normalized bbox to pixels without applying workflow policies."""
    normalized = normalize_unit_bbox(crop_bbox)
    if normalized == {}:
        return (0, 0, image.width, image.height)
    x, y, width, height = normalized
    left = min(max(round(x * image.width), 0), image.width - 1)
    top = min(max(round(y * image.height), 0), image.height - 1)
    right = min(max(round((x + width) * image.width), left + 1), image.width)
    bottom = min(max(round((y + height) * image.height), top + 1), image.height)
    return left, top, right, bottom


def pixel_crop_box(image: Image.Image, crop_bbox: Any) -> tuple[int, int, int, int]:
    normalized = normalize_draft_bbox(crop_bbox)
    return normalized_bbox_pixel_box(image, normalized)


def create_cropped_temp_image(source_path: str | Path, crop_bbox: Any) -> Path | None:
    """Create a private JPEG crop for processing, or return None for full-image Drafts."""
    if is_full_image_bbox(crop_bbox):
        return None
    with Image.open(source_path) as image:
        cropped = image.convert("RGB").crop(pixel_crop_box(image, crop_bbox))
        cropped.load()
    output = settings.UPLOAD_DIR_PATH / f"tmp_draft_crop_{uuid.uuid4().hex}.jpg"
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        cropped.save(output, format="JPEG", quality=95)
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return output


def render_draft_image(source_path: str | Path, crop_bbox: Any) -> tuple[bytes, str]:
    """Return the exact image represented by a Draft for its authenticated endpoint."""
    with Image.open(source_path) as image:
        if is_full_image_bbox(crop_bbox):
            rendered = image.copy()
        else:
            rendered = image.crop(pixel_crop_box(image, crop_bbox))
        rendered.load()
        if rendered.mode not in ("RGB", "L"):
            rendered = rendered.convert("RGB")

    from io import BytesIO

    buffer = BytesIO()
    rendered.save(buffer, format="PNG")
    return buffer.getvalue(), "image/png"


def compose_bbox_to_page(crop_bbox: Any, relative_bbox: Any) -> list[float] | None:
    """Compose a crop-relative normalized bbox into original-page coordinates."""
    try:
        relative = normalize_unit_bbox(relative_bbox)
        crop = normalize_draft_bbox(crop_bbox)
    except ValueError:
        return None
    if relative == {}:
        return None
    if crop == {}:
        return relative
    crop_x, crop_y, crop_width, crop_height = crop
    x, y, width, height = relative
    return [
        round(crop_x + x * crop_width, 6),
        round(crop_y + y * crop_height, 6),
        round(width * crop_width, 6),
        round(height * crop_height, 6),
    ]
