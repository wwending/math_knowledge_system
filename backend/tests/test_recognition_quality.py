import unittest

from app.services.recognition_quality import (
    detect_option_labels,
    detect_quality_warnings,
    extract_option_markers,
)


class RecognitionQualityTests(unittest.TestCase):
    def test_detect_option_labels_supports_common_choice_formats(self):
        text = "A. 1\nB．2\nC、3\nD）4"

        self.assertEqual(detect_option_labels(text), {"A", "B", "C", "D"})
        self.assertEqual(extract_option_markers(text), ["A", "B", "C", "D"])

    def test_detect_option_labels_supports_ascii_and_chinese_parentheses(self):
        text = "(A) 选项一\n（B）选项二\n(C) 选项三\n（D）选项四"

        self.assertEqual(extract_option_markers(text), ["A", "B", "C", "D"])

    def test_math_context_letters_are_not_option_markers(self):
        text = """在 △ABC 中，三角形 ABC 的内角 A、B、C 分别对应边 a, b, c。
∠A = 30°，角 A 与 sin B、cos A 有关。
点 A、B、C 共线，边 AB 满足 AB = AC。
A = 30°"""

        self.assertEqual(extract_option_markers(text), [])
        self.assertNotIn(
            "choice_options_incomplete",
            [warning.code for warning in detect_quality_warnings(text)],
        )

    def test_fill_blank_regression_does_not_return_choice_warning(self):
        text = """在 △ABC 中，内角 A、B、C 的对边分别为 a、b、c，
若 b sin C + a sin A = b sin B + c sin C，
则内角 A = ____

若 D 是边 BC 的中点，c = 2，AD = sqrt(13)，则 d = ____"""

        warning_codes = [warning.code for warning in detect_quality_warnings(text)]

        self.assertEqual(extract_option_markers(text), [])
        self.assertNotIn("choice_options_incomplete", warning_codes)

    def test_question_type_without_structured_markers_does_not_return_choice_warning(self):
        warnings = detect_quality_warnings("在△ABC中，∠A = 30°", question_type="single_choice")

        self.assertNotIn("choice_options_incomplete", [warning.code for warning in warnings])

    def test_choice_with_only_two_options_returns_incomplete_warning(self):
        warnings = detect_quality_warnings("已知函数 f(x)，则（ ）\nA. 1\nB. 2")

        self.assertIn("choice_options_incomplete", [warning.code for warning in warnings])
        self.assertIn("当前只检测到 2 个选项", warnings[0].message)

    def test_single_structured_marker_is_not_enough_to_infer_choice_question(self):
        warnings = detect_quality_warnings("题目正文足够长，不应仅凭一个标记判断。\nA. 单独的小节")

        self.assertNotIn("choice_options_incomplete", [warning.code for warning in warnings])

    def test_three_ascii_dot_options_return_incomplete_warning(self):
        warnings = detect_quality_warnings("A. 选项一\nB. 选项二\nC. 选项三")

        self.assertIn("choice_options_incomplete", [warning.code for warning in warnings])

    def test_three_chinese_parenthesized_options_return_incomplete_warning(self):
        warnings = detect_quality_warnings("（A）选项一\n（B）选项二\n（C）选项三")

        self.assertIn("choice_options_incomplete", [warning.code for warning in warnings])

    def test_choice_with_gap_returns_sequence_gap_warning(self):
        warnings = detect_quality_warnings("若 x>0，则（ ）\nA. x\nC. x^2")

        self.assertIn("choice_options_sequence_gap", [warning.code for warning in warnings])

    def test_complete_choice_options_do_not_return_incomplete_warning(self):
        warnings = detect_quality_warnings("A.\nB.\nC.\nD.")

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
