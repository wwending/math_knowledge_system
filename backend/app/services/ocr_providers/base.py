from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol


@dataclass
class OCRResult:
    text: str
    provider: str
    confidence: Optional[float] = None
    boxes: list[Any] = field(default_factory=list)
    raw_response_summary: dict[str, Any] = field(default_factory=dict)
    latency_ms: int = 0
    error: Optional[str] = None
    error_type: Optional[str] = None
    detail: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None


class OcrProvider(Protocol):
    provider_name: str

    def recognize(self, image_path: str) -> OCRResult:
        ...
