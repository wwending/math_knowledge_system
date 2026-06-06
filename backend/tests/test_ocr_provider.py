import unittest

from app.core.config import settings
from app.services.ocr_providers.baidu import BaiduOcrProvider
from app.services.ocr_service import OCRService


class FakeLegacyOcrEngine:
    ocr_url = "https://example.test/baidu-ocr"

    def __init__(self, result):
        self.result = result
        self.calls = []

    def recognize(self, image_path: str):
        self.calls.append(image_path)
        return self.result


class OcrProviderTests(unittest.TestCase):
    def test_baidu_provider_wraps_legacy_engine_success_result(self):
        legacy_result = {
            "success": True,
            "content": "百度 OCR 文本",
            "cost_seconds": 0.12,
        }
        legacy_engine = FakeLegacyOcrEngine(legacy_result)
        provider = BaiduOcrProvider(engine=legacy_engine)

        result = provider.recognize("sample.png")

        self.assertEqual(legacy_engine.calls, ["sample.png"])
        self.assertEqual(result.provider, "baidu")
        self.assertEqual(result.text, "百度 OCR 文本")
        self.assertEqual(result.latency_ms, 120)
        self.assertIsNone(result.error)
        self.assertEqual(result.raw_response_summary["success"], True)
        self.assertEqual(result.raw_response_summary["content"], "百度 OCR 文本")

    def test_baidu_provider_wraps_legacy_engine_failure_result(self):
        legacy_result = {
            "success": False,
            "content": "",
            "cost_seconds": 0.03,
            "error_type": "timeout",
            "error": "ocr timeout",
            "detail": "baidu_ocr_timeout",
        }
        provider = BaiduOcrProvider(engine=FakeLegacyOcrEngine(legacy_result))

        result = provider.recognize("sample.png")

        self.assertEqual(result.provider, "baidu")
        self.assertEqual(result.text, "")
        self.assertEqual(result.latency_ms, 30)
        self.assertEqual(result.error, "ocr timeout")
        self.assertEqual(result.error_type, "timeout")
        self.assertEqual(result.detail, "baidu_ocr_timeout")

    def test_ocr_service_selects_baidu_provider_from_settings(self):
        old_provider = settings.OCR_PROVIDER
        settings.OCR_PROVIDER = "baidu"
        try:
            service = OCRService(provider_factories={"baidu": lambda: BaiduOcrProvider(engine=FakeLegacyOcrEngine({
                "success": True,
                "content": "service text",
                "cost_seconds": 0.01,
            }))})

            result = service.recognize("sample.png")
        finally:
            settings.OCR_PROVIDER = old_provider

        self.assertEqual(result.provider, "baidu")
        self.assertEqual(result.text, "service text")
        self.assertIsNone(result.error)

    def test_ocr_service_returns_clear_failure_for_unknown_provider(self):
        old_provider = settings.OCR_PROVIDER
        settings.OCR_PROVIDER = "rapidocr"
        try:
            service = OCRService(provider_factories={"baidu": lambda: BaiduOcrProvider(engine=FakeLegacyOcrEngine({
                "success": True,
                "content": "unused",
                "cost_seconds": 0.01,
            }))})

            result = service.recognize("sample.png")
        finally:
            settings.OCR_PROVIDER = old_provider

        self.assertEqual(result.provider, "rapidocr")
        self.assertEqual(result.text, "")
        self.assertEqual(result.error_type, "unsupported_provider")
        self.assertEqual(result.detail, "unsupported_ocr_provider:rapidocr")
        self.assertIn("Unsupported OCR provider", result.error)


if __name__ == "__main__":
    unittest.main()
