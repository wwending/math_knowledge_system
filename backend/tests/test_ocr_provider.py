import unittest
from unittest.mock import patch

from app.core.config import settings
from app.services.ocr_providers.baidu import BaiduOcrProvider
from app.services.ocr_providers.rapidocr import RapidOcrProvider, parse_rapidocr_result
from app.services.ocr_service import OCRService


class FakeLegacyOcrEngine:
    ocr_url = "https://example.test/baidu-ocr"

    def __init__(self, result):
        self.result = result
        self.calls = []

    def recognize(self, image_path: str):
        self.calls.append(image_path)
        return self.result


class FakeRapidOcrEngine:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def __call__(self, image_path: str):
        self.calls.append(image_path)
        return self.result


class FakeRapidOcrObjectResult:
    txts = ["第一行", "", "第二行"]
    boxes = [[[0, 0], [10, 0], [10, 10], [0, 10]]]
    scores = [0.98]


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

    def test_ocr_service_defaults_to_baidu_provider_when_setting_is_empty(self):
        old_provider = settings.OCR_PROVIDER
        settings.OCR_PROVIDER = ""
        try:
            service = OCRService(provider_factories={"baidu": lambda: BaiduOcrProvider(engine=FakeLegacyOcrEngine({
                "success": True,
                "content": "default provider text",
                "cost_seconds": 0.01,
            }))})

            result = service.recognize("sample.png")
        finally:
            settings.OCR_PROVIDER = old_provider

        self.assertEqual(result.provider, "baidu")
        self.assertEqual(result.text, "default provider text")

    def test_ocr_service_selects_rapidocr_provider_from_settings(self):
        old_provider = settings.OCR_PROVIDER
        settings.OCR_PROVIDER = "rapidocr"
        try:
            service = OCRService(provider_factories={
                "baidu": lambda: BaiduOcrProvider(engine=FakeLegacyOcrEngine({
                    "success": True,
                    "content": "unused",
                    "cost_seconds": 0.01,
                })),
                "rapidocr": lambda: RapidOcrProvider(engine=FakeRapidOcrEngine([
                    ([[0, 0], [1, 0], [1, 1], [0, 1]], "rapid text", 0.9),
                ])),
            })

            result = service.recognize("sample.png")
        finally:
            settings.OCR_PROVIDER = old_provider

        self.assertEqual(result.provider, "rapidocr")
        self.assertEqual(result.text, "rapid text")
        self.assertIsNone(result.error)

    def test_ocr_service_can_override_provider_per_recognize_call(self):
        old_provider = settings.OCR_PROVIDER
        settings.OCR_PROVIDER = "baidu"
        try:
            service = OCRService(provider_factories={
                "baidu": lambda: BaiduOcrProvider(engine=FakeLegacyOcrEngine({
                    "success": True,
                    "content": "default baidu text",
                    "cost_seconds": 0.01,
                })),
                "rapidocr": lambda: RapidOcrProvider(engine=FakeRapidOcrEngine([
                    ([[0, 0], [1, 0], [1, 1], [0, 1]], "override rapid text", 0.9),
                ])),
            })

            result = service.recognize("sample.png", provider_name="rapidocr")
        finally:
            settings.OCR_PROVIDER = old_provider

        self.assertEqual(result.provider, "rapidocr")
        self.assertEqual(result.text, "override rapid text")
        self.assertIsNone(result.error)

    def test_ocr_service_caches_selected_provider_instance(self):
        old_provider = settings.OCR_PROVIDER
        settings.OCR_PROVIDER = "rapidocr"
        factory_calls = []
        fake_engine = FakeRapidOcrEngine([
            ([[0, 0], [1, 0], [1, 1], [0, 1]], "cached text", 0.9),
        ])

        def build_provider():
            factory_calls.append("called")
            return RapidOcrProvider(engine=fake_engine)

        try:
            service = OCRService(provider_factories={"rapidocr": build_provider})

            first_result = service.recognize("first.png")
            second_result = service.recognize("second.png")
        finally:
            settings.OCR_PROVIDER = old_provider

        self.assertEqual(factory_calls, ["called"])
        self.assertEqual(fake_engine.calls, ["first.png", "second.png"])
        self.assertEqual(first_result.text, "cached text")
        self.assertEqual(second_result.text, "cached text")

    def test_rapidocr_provider_raises_clear_error_when_dependency_missing(self):
        provider = RapidOcrProvider()
        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "rapidocr":
                raise ImportError("missing rapidocr")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaisesRegex(RuntimeError, "pip install rapidocr"):
                provider.recognize("sample.png")

    def test_parse_rapidocr_list_of_tuples(self):
        parsed = parse_rapidocr_result([
            ([[0, 0], [1, 0], [1, 1], [0, 1]], "第一行", 0.91),
            ([[0, 2], [1, 2], [1, 3], [0, 3]], "", 0.1),
            ([[0, 4], [1, 4], [1, 5], [0, 5]], "第二行", 0.88),
        ])

        self.assertEqual(parsed.text, "第一行\n第二行")
        self.assertEqual(len(parsed.boxes), 2)
        self.assertEqual(parsed.scores, [0.91, 0.88])

    def test_parse_rapidocr_object_with_txts(self):
        parsed = parse_rapidocr_result(FakeRapidOcrObjectResult())

        self.assertEqual(parsed.text, "第一行\n第二行")
        self.assertEqual(parsed.boxes, FakeRapidOcrObjectResult.boxes)
        self.assertEqual(parsed.scores, FakeRapidOcrObjectResult.scores)

    def test_parse_rapidocr_empty_result_returns_empty_text(self):
        parsed = parse_rapidocr_result([])

        self.assertEqual(parsed.text, "")
        self.assertEqual(parsed.boxes, [])
        self.assertEqual(parsed.scores, [])

    def test_parse_rapidocr_unrecognized_shape_raises_clear_error(self):
        with self.assertRaisesRegex(ValueError, "Unsupported RapidOCR result format"):
            parse_rapidocr_result({"unexpected": "shape"})

    def test_ocr_service_returns_clear_failure_for_unknown_provider(self):
        old_provider = settings.OCR_PROVIDER
        settings.OCR_PROVIDER = "unknown"
        try:
            service = OCRService(provider_factories={"baidu": lambda: BaiduOcrProvider(engine=FakeLegacyOcrEngine({
                "success": True,
                "content": "unused",
                "cost_seconds": 0.01,
            }))})

            result = service.recognize("sample.png")
        finally:
            settings.OCR_PROVIDER = old_provider

        self.assertEqual(result.provider, "unknown")
        self.assertEqual(result.text, "")
        self.assertEqual(result.error_type, "unsupported_provider")
        self.assertEqual(result.detail, "unsupported_ocr_provider:unknown")
        self.assertEqual(result.error, "Unsupported OCR_PROVIDER: unknown. Supported values: baidu.")


if __name__ == "__main__":
    unittest.main()
