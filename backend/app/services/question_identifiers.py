from __future__ import annotations

from typing import Any
from uuid import UUID


def canonical_uuid(value: Any) -> str:
    return str(UUID(str(value)))
