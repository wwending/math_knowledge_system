import json
import unittest
from pathlib import Path

from app.services.ocr_evaluation import (
    evaluate_ocr_batch,
    evaluate_ocr_prediction,
    normalize_ocr_text,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures"


class OcrEvaluationTests(unittest.TestCase):
    def test_normalize_ocr_text_collapses_extra_whitespace_and_newlines(self):
        text = "  f(x)  =  x^2\n\n + 1\t "

        self.assertEqual(normalize_ocr_text(text), "f(x) = x^2 + 1")

    def test_exact_text_sets_exact_and_normalized_match(self):
        metrics = evaluate_ocr_prediction(
            expected_text="Solve x^2 - 1 = 0",
            predicted_text="Solve x^2 - 1 = 0",
        )

        self.assertTrue(metrics.exact_match)
        self.assertTrue(metrics.normalized_exact_match)
        self.assertEqual(metrics.similarity_ratio, 1.0)
        self.assertEqual(metrics.length_delta, 0)

    def test_minor_ocr_difference_has_partial_similarity(self):
        metrics = evaluate_ocr_prediction(
            expected_text="triangle ABC has angle A = 60",
            predicted_text="triangle ABC has angle A = 6O",
        )

        self.assertFalse(metrics.exact_match)
        self.assertFalse(metrics.normalized_exact_match)
        self.assertGreater(metrics.similarity_ratio, 0)
        self.assertLess(metrics.similarity_ratio, 1)

    def test_required_terms_recall_counts_hits(self):
        metrics = evaluate_ocr_prediction(
            expected_text="Given f(x)=x^2+1 and x in R",
            predicted_text="Given f(x)=x^2+1",
            required_terms=["f(x)", "x^2+1", "x in R"],
        )

        self.assertEqual(metrics.required_terms_total, 3)
        self.assertEqual(metrics.required_terms_hit, 2)
        self.assertAlmostEqual(metrics.required_terms_recall, 2 / 3)

    def test_batch_evaluation_groups_metrics_by_provider(self):
        cases = json.loads((FIXTURE_DIR / "ocr_eval_cases.json").read_text(encoding="utf-8"))
        predictions = json.loads(
            (FIXTURE_DIR / "ocr_eval_predictions.json").read_text(encoding="utf-8")
        )

        summary = evaluate_ocr_batch(cases, predictions)

        self.assertEqual(summary.total_cases, 4)
        self.assertEqual(summary.total_predictions, 4)
        self.assertIn("baidu", summary.by_provider)
        self.assertIn("rapidocr-placeholder", summary.by_provider)
        self.assertEqual(summary.by_provider["baidu"].total_predictions, 2)
        self.assertGreater(summary.by_provider["baidu"].avg_similarity_ratio, 0)

    def test_batch_evaluation_handles_missing_prediction_and_error_without_crashing(self):
        cases = [
            {
                "case_id": "missing-case",
                "image_path": "local-only/missing.png",
                "expected_text": "expected text",
                "category": "algebra",
                "required_terms": ["expected"],
            },
            {
                "case_id": "error-case",
                "image_path": "local-only/error.png",
                "expected_text": "expected text",
                "category": "function",
                "required_terms": ["expected"],
            },
        ]
        predictions = [
            {
                "case_id": "error-case",
                "provider": "baidu",
                "predicted_text": "",
                "latency_ms": 42,
                "error": "ocr timeout",
            }
        ]

        summary = evaluate_ocr_batch(cases, predictions)

        self.assertEqual(summary.missing_predictions_count, 1)
        self.assertEqual(summary.error_predictions_count, 1)
        missing_records = [record for record in summary.records if record.case_id == "missing-case"]
        error_records = [record for record in summary.records if record.case_id == "error-case"]
        self.assertEqual(missing_records[0].metrics.error, "missing_prediction")
        self.assertEqual(error_records[0].metrics.error, "ocr timeout")
        self.assertEqual(summary.by_provider["baidu"].error_count, 1)


if __name__ == "__main__":
    unittest.main()
