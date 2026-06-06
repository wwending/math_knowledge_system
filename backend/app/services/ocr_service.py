from __future__ import annotations

from collections.abc import Callable

from loguru import logger

from app.core.config import settings
from app.services.ocr_providers.baidu import BaiduOcrProvider
from app.services.ocr_providers.base import OCRResult, OcrProvider


class OCRService:
    def __init__(self, provider_factories: dict[str, Callable[[], OcrProvider]] | None = None):
        self.provider_factories = provider_factories or {
            "baidu": BaiduOcrProvider,
        }

    @property
    def provider_name(self) -> str:
        return (settings.OCR_PROVIDER or "baidu").strip().lower()

    @property
    def endpoint(self) -> str | None:
        provider = self._get_provider()
        return getattr(provider, "endpoint", None) if provider else None

    def recognize(self, image_path: str) -> OCRResult:
        provider_name = self.provider_name
        provider = self._get_provider()
        if provider is None:
            logger.warning("Unsupported OCR provider configured: {}", provider_name)
            return OCRResult(
                text="",
                provider=provider_name,
                raw_response_summary={"provider": provider_name, "success": False},
                latency_ms=0,
                error=f"Unsupported OCR provider: {provider_name}",
                error_type="unsupported_provider",
                detail=f"unsupported_ocr_provider:{provider_name}",
            )
        return provider.recognize(image_path)

    def _get_provider(self) -> OcrProvider | None:
        factory = self.provider_factories.get(self.provider_name)
        if factory is None:
            return None
        return factory()


ocr_service = OCRService()
