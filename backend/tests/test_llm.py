import unittest

from app.services.llm import NLPService, normalize_latex_delimiters


class FakeMessage:
    content = (
        '{"corrected_text": "已知 \\\\(\\\\triangle ABC\\\\)，且 \\\\[x^2 + y^2 = z^2\\\\]", '
        '"tags": ["三角形", "勾股定理", "解析几何"]}'
    )


class FakeChoice:
    message = FakeMessage()


class FakeResponse:
    choices = [FakeChoice()]


class FakeCompletions:
    def create(self, **kwargs):
        return FakeResponse()


class FakeChat:
    completions = FakeCompletions()


class FakeClient:
    chat = FakeChat()


class NormalizeLatexDelimitersTest(unittest.TestCase):
    def test_inline_triangle_delimiters(self):
        self.assertEqual(
            normalize_latex_delimiters(r"\(\triangle ABC\)"),
            r"$\triangle ABC$",
        )

    def test_inline_fraction_delimiters(self):
        self.assertEqual(
            normalize_latex_delimiters(r"\(\frac{a}{b}\)"),
            r"$\frac{a}{b}$",
        )

    def test_block_delimiters(self):
        self.assertEqual(
            normalize_latex_delimiters(r"\[x^2 + y^2 = z^2\]"),
            r"$$x^2 + y^2 = z^2$$",
        )

    def test_existing_inline_dollar_delimiters_are_unchanged(self):
        self.assertEqual(normalize_latex_delimiters("$x$"), "$x$")

    def test_existing_block_dollar_delimiters_are_unchanged(self):
        self.assertEqual(normalize_latex_delimiters("$$x^2$$"), "$$x^2$$")

    def test_chinese_text_is_unchanged(self):
        self.assertEqual(normalize_latex_delimiters("求函数的定义域。"), "求函数的定义域。")

    def test_empty_string_is_safe(self):
        self.assertEqual(normalize_latex_delimiters(""), "")


class NLPServiceAnalyzeTest(unittest.TestCase):
    def test_analyze_normalizes_latex_delimiters_in_success_result(self):
        service = object.__new__(NLPService)
        service.client = FakeClient()

        result = service.analyze("OCR text")

        self.assertIs(result["success"], True)
        self.assertIn(r"$\triangle ABC$", result["corrected_text"])
        self.assertIn(r"$$x^2 + y^2 = z^2$$", result["corrected_text"])
        self.assertNotIn(r"\(", result["corrected_text"])
        self.assertNotIn(r"\)", result["corrected_text"])
        self.assertNotIn(r"\[", result["corrected_text"])
        self.assertNotIn(r"\]", result["corrected_text"])
        self.assertEqual(result["tags"], ["三角形", "勾股定理", "解析几何"])


if __name__ == "__main__":
    unittest.main()
