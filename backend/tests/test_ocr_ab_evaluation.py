import json
import tempfile
import unittest
from pathlib import Path

from app.services.ocr_providers.base import OCRResult
from scripts.evaluation.compare_ocr_providers import (
    collect_image_paths,
    render_markdown_report,
    run_comparison,
    write_outputs,
)


class FakeOcrService:
    def __init__(self):
        self.calls = []

    def recognize(self, image_path: str, provider_name: str | None = None):
        self.calls.append((Path(image_path).name, provider_name))
        if provider_name == "broken":
            raise RuntimeError("provider exploded")
        if provider_name == "baidu":
            return OCRResult(
                text="已知函数 f(x)，则（ ）\nA. 1\nB. 2",
                provider="baidu",
                latency_ms=12,
            )
        return OCRResult(
            text="rapid text",
            provider=provider_name or "rapidocr",
            latency_ms=34,
        )


class FakeLlmService:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls = []

    def analyze(self, text: str):
        self.calls.append(text)
        if self.fail:
            raise RuntimeError("llm exploded")
        return {
            "success": True,
            "corrected_text": f"cleaned {text}",
            "knowledge_tags": ["函数"],
        }


class OcrAbEvaluationTests(unittest.TestCase):
    def test_collect_image_paths_accepts_file_or_sorted_image_directory(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "b.png").write_bytes(b"png")
            (root / "a.jpg").write_bytes(b"jpg")
            (root / "ignore.txt").write_text("skip", encoding="utf-8")

            images = collect_image_paths(root)

            self.assertEqual([path.name for path in images], ["a.jpg", "b.png"])
            self.assertEqual(collect_image_paths(root / "b.png"), [root / "b.png"])

    def test_run_comparison_records_each_provider_and_keeps_going_after_failure(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            image = Path(tmp_dir) / "sample.png"
            image.write_bytes(b"image")

            results = run_comparison(
                input_path=image,
                providers=["baidu", "broken", "rapidocr"],
                with_llm=False,
                ocr_service=FakeOcrService(),
                llm_service=FakeLlmService(),
            )

        self.assertEqual([item["provider"] for item in results], ["baidu", "broken", "rapidocr"])
        self.assertTrue(results[0]["success"])
        self.assertFalse(results[1]["success"])
        self.assertIn("provider exploded", results[1]["error_message"])
        self.assertTrue(results[2]["success"])
        self.assertIn("choice_options_incomplete", results[0]["quality_warnings"])
        self.assertEqual(results[0]["manual_conclusion"], "")
        self.assertEqual(results[0]["notes"], "")

    def test_run_comparison_only_calls_llm_when_enabled_and_records_failure(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            image = Path(tmp_dir) / "sample.png"
            image.write_bytes(b"image")
            llm_service = FakeLlmService(fail=True)

            results = run_comparison(
                input_path=image,
                providers=["baidu"],
                with_llm=True,
                ocr_service=FakeOcrService(),
                llm_service=llm_service,
            )

        self.assertEqual(len(llm_service.calls), 1)
        self.assertTrue(results[0]["llm_enabled"])
        self.assertFalse(results[0]["llm_success"])
        self.assertIn("llm exploded", results[0]["llm_error_message"])

    def test_write_outputs_writes_markdown_and_optional_json(self):
        results = [
            {
                "image_path": "sample.png",
                "image_name": "sample.png",
                "provider": "baidu",
                "success": True,
                "error_message": "",
                "elapsed_ms": 12,
                "raw_text": "raw text",
                "raw_text_length": 8,
                "quality_warnings": [],
                "llm_enabled": False,
                "llm_success": False,
                "llm_error_message": "",
                "llm_corrected_text": "",
                "llm_tags": [],
                "knowledge_tags": [],
                "manual_conclusion": "",
                "notes": "",
            }
        ]
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "reports" / "ocr_ab.md"
            json_output = Path(tmp_dir) / "reports" / "ocr_ab.json"

            write_outputs(
                results,
                output_path=output,
                json_output_path=json_output,
                input_value="sample.png",
                providers=["baidu"],
                with_llm=False,
            )

            markdown = output.read_text(encoding="utf-8")
            payload = json.loads(json_output.read_text(encoding="utf-8"))

        self.assertIn("# OCR Provider A/B Smoke Report", markdown)
        self.assertIn("| sample.png | baidu | yes | 12 | 8 |", markdown)
        self.assertEqual(payload["results"][0]["provider"], "baidu")
        self.assertEqual(payload["metadata"]["providers"], ["baidu"])

    def test_render_markdown_report_includes_manual_conclusion_suggestions(self):
        markdown = render_markdown_report(
            [],
            generated_at="2026-06-17T00:00:00+08:00",
            input_value="static/uploads_test",
            providers=["baidu", "rapidocr"],
            with_llm=False,
        )

        self.assertIn("manual_conclusion 建议值", markdown)
        self.assertIn("usable", markdown)


if __name__ == "__main__":
    unittest.main()
