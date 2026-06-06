from __future__ import annotations

from typing import Any

from app.services.ocr_engine import OCREngine, ocr_service as default_baidu_engine
from app.services.ocr_providers.base import OCRResult


class BaiduOcrProvider:
    provider_name = "baidu"

    def __init__(self, engine: OCREngine | None = None):
        self.engine = engine or default_baidu_engine

    @property
    def endpoint(self) -> str | None:
        return getattr(self.engine, "ocr_url", None)

    def recognize(self, image_path: str) -> OCRResult:
        legacy_result = self.engine.recognize(image_path)
        return self._from_legacy_result(legacy_result)

    def _from_legacy_result(self, legacy_result: dict[str, Any]) -> OCRResult:
        latency_ms = int(float(legacy_result.get("cost_seconds") or 0) * 1000)
        success = bool(legacy_result.get("success"))
        return OCRResult(
            text=str(legacy_result.get("content") or ""),
            provider=self.provider_name,
            confidence=None,
            boxes=[],
            raw_response_summary=dict(legacy_result),
            latency_ms=latency_ms,
            error=None if success else legacy_result.get("error"),
            error_type=None if success else legacy_result.get("error_type"),
            detail=None if success else legacy_result.get("detail"),
        )
