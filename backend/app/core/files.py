"""Shared upload-file path resolution.

Extracted from the API layer (#59) so services can resolve stored upload
references without importing from app.api, which would create an import cycle.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from app.core.config import settings


def resolve_upload_file_path(raw_path: Optional[str]) -> Optional[str]:
    """Resolve a stored upload reference to a file inside UPLOAD_DIR_PATH.

    Stored values are bare filenames written by the upload pipelines. Legacy rows may
    still carry a "/static/uploads/..." URL or an "uploads/..." prefix, so both forms
    are tolerated and resolved against the (now relocated) uploads directory. Absolute
    paths are accepted for parity with _asset_file_path, but resolution is always
    contained to UPLOAD_DIR_PATH so a tampered DB row cannot read arbitrary files.
    """
    normalized = str(raw_path or "").strip()
    if not normalized or normalized.startswith(("http://", "https://")):
        return None

    static_prefix = f"{settings.STATIC_URL_PREFIX_NORMALIZED}/"
    if normalized.startswith(static_prefix):
        normalized = normalized[len(static_prefix):]
    normalized = normalized.lstrip("/").replace("\\", "/")
    if not normalized:
        return None

    candidates = [normalized]
    uploads_segment = "uploads/"
    if normalized.startswith(uploads_segment):
        candidates.append(normalized[len(uploads_segment):])

    upload_root = settings.UPLOAD_DIR_PATH.resolve()
    for candidate_name in candidates:
        candidate = (
            Path(candidate_name)
            if os.path.isabs(candidate_name)
            else upload_root / candidate_name
        )
        resolved = candidate.resolve()
        if resolved != upload_root and upload_root not in resolved.parents:
            continue
        if resolved.is_file():
            return str(resolved)
    return None
