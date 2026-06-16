import unittest

from app.services.recognition_quality import (
    detect_option_labels,
    detect_quality_warnings,
)


class RecognitionQualityTests(unittest.TestCase):
    def test_detect_option_labels_supports_common_choice_formats(self):
        text = "A. 1\nB．2\nC、3\nD）4"

        self.assertEqual(detect_option_labels(text), {"A", "B", "C", "D"})

    def test_choice_with_only_two_options_returns_incomplete_warning(self):
        warnings = detect_quality_warnings("已知函数 f(x)，则（ ）\nA. 1\nB. 2")

        self.assertIn("choice_options_incomplete", [warning.code for warning in warnings])
        self.assertIn("当前只检测到 2 个选项", warnings[0].message)

    def test_choice_with_gap_returns_sequence_gap_warning(self):
        warnings = detect_quality_warnings("若 x>0，则（ ）\nA. x\nC. x^2")

        self.assertIn("choice_options_sequence_gap", [warning.code for warning in warnings])

    def test_complete_choice_options_do_not_return_incomplete_warning(self):
        warnings = detect_quality_warnings("若 x>0，则（ ）\nA. 1\nB. 2\nC. 3\nD. 4")

        self.assertNotIn("choice_options_incomplete", [warning.code for warning in warnings])

    def test_short_recognized_text_returns_warning(self):
        warnings = detect_quality_warnings("求 x")

        self.assertIn("recognized_text_too_short", [warning.code for warning in warnings])

    def test_large_ocr_llm_length_difference_returns_warning(self):
        raw_ocr_text = "A. 1 B. 2 C. 3 D. 4 " * 5
        llm_cleaned_text = "A. 1 B. 2"

        warnings = detect_quality_warnings(
            llm_cleaned_text,
            raw_ocr_text=raw_ocr_text,
            llm_cleaned_text=llm_cleaned_text,
        )

        self.assertIn("ocr_llm_text_changed_substantially", [warning.code for warning in warnings])


if __name__ == "__main__":
    unittest.main()
