from __future__ import annotations

from collections.abc import Callable

from loguru import logger

from app.core.config import settings
from app.services.ocr_providers.baidu import BaiduOcrProvider
from app.services.ocr_providers.base import OCRResult, OcrProvider
from app.services.ocr_providers.rapidocr import RapidOcrProvider


class OCRService:
    def __init__(self, provider_factories: dict[str, Callable[[], OcrProvider]] | None = None):
        self.provider_factories = provider_factories or {
            "baidu": BaiduOcrProvider,
            "rapidocr": RapidOcrProvider,
        }
        self._provider_cache: dict[str, OcrProvider] = {}

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
            supported_values = ", ".join(sorted(self.provider_factories))
            return OCRResult(
                text="",
                provider=provider_name,
                raw_response_summary={"provider": provider_name, "success": False},
                latency_ms=0,
                error=f"Unsupported OCR_PROVIDER: {provider_name}. Supported values: {supported_values}.",
                error_type="unsupported_provider",
                detail=f"unsupported_ocr_provider:{provider_name}",
            )
        return provider.recognize(image_path)

    def _get_provider(self) -> OcrProvider | None:
        provider_name = self.provider_name
        factory = self.provider_factories.get(provider_name)
        if factory is None:
            return None
        if provider_name not in self._provider_cache:
            self._provider_cache[provider_name] = factory()
        return self._provider_cache[provider_name]


ocr_service = OCRService()
