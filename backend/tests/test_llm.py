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
    def test_analyze_defaults_to_lightweight_text_contract(self):
        class MetadataMessage:
            content = (
                '{"corrected_text": "clean text", '
                '"knowledge_tags": ["圆与方程"], '
                '"question_type": "single_choice", '
                '"difficulty": {"level": 3, "label": "中等", "confidence": 0.78, '
                '"reason": "涉及两步推理。"}}'
            )

        class MetadataChoice:
            message = MetadataMessage()

        class MetadataResponse:
            choices = [MetadataChoice()]

        class MetadataCompletions:
            def create(self, **kwargs):
                return MetadataResponse()

        class MetadataChat:
            completions = MetadataCompletions()

        class MetadataClient:
            chat = MetadataChat()

        service = object.__new__(NLPService)
        service.client = MetadataClient()

        result = service.analyze("OCR text")

        self.assertIs(result["success"], True)
        self.assertEqual(result["corrected_text"], "clean text")
        self.assertEqual(result["knowledge_tags"], ["圆与方程"])
        self.assertEqual(result["question_type"], "unknown")
        self.assertIsNone(result["difficulty"])

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

    def test_analyze_accepts_new_question_metadata_contract_when_requested(self):
        class MetadataMessage:
            content = (
                '{"corrected_text": "clean text", '
                '"knowledge_tags": ["圆与方程", "切线"], '
                '"question_type": "single_choice", '
                '"difficulty": {"level": 3, "label": "中等", "confidence": 0.78, '
                '"reason": "涉及圆的切线方程与参数代入，需要两步推理。"}}'
            )

        class MetadataChoice:
            message = MetadataMessage()

        class MetadataResponse:
            choices = [MetadataChoice()]

        class MetadataCompletions:
            def create(self, **kwargs):
                return MetadataResponse()

        class MetadataChat:
            completions = MetadataCompletions()

        class MetadataClient:
            chat = MetadataChat()

        service = object.__new__(NLPService)
        service.client = MetadataClient()

        result = service.analyze("OCR text", include_metadata=True)

        self.assertIs(result["success"], True)
        self.assertEqual(result["corrected_text"], "clean text")
        self.assertEqual(result["knowledge_tags"], ["圆与方程", "切线"])
        self.assertEqual(result["tags"], ["圆与方程", "切线"])
        self.assertEqual(result["question_type"], "single_choice")
        self.assertEqual(
            result["difficulty"],
            {
                "level": 3,
                "label": "中等",
                "confidence": 0.78,
                "reason": "涉及圆的切线方程与参数代入，需要两步推理。",
            },
        )

    def test_analyze_keeps_legacy_tags_contract_compatible(self):
        service = object.__new__(NLPService)
        service.client = FakeClient()

        result = service.analyze("OCR text", include_metadata=True)

        self.assertIs(result["success"], True)
        self.assertEqual(result["tags"], ["三角形", "勾股定理", "解析几何"])
        self.assertEqual(result["knowledge_tags"], ["三角形", "勾股定理", "解析几何"])
        self.assertEqual(result["question_type"], "unknown")
        self.assertIsNone(result["difficulty"])

    def test_analyze_allows_missing_difficulty(self):
        class MissingDifficultyMessage:
            content = '{"corrected_text": "clean text", "knowledge_tags": ["函数"], "question_type": "solution"}'

        class MissingDifficultyChoice:
            message = MissingDifficultyMessage()

        class MissingDifficultyResponse:
            choices = [MissingDifficultyChoice()]

        class MissingDifficultyCompletions:
            def create(self, **kwargs):
                return MissingDifficultyResponse()

        class MissingDifficultyChat:
            completions = MissingDifficultyCompletions()

        class MissingDifficultyClient:
            chat = MissingDifficultyChat()

        service = object.__new__(NLPService)
        service.client = MissingDifficultyClient()

        result = service.analyze("OCR text", include_metadata=True)

        self.assertIs(result["success"], True)
        self.assertEqual(result["corrected_text"], "clean text")
        self.assertIsNone(result["difficulty"])

    def test_evaluate_question_metadata_returns_metadata_only(self):
        class MetadataMessage:
            content = (
                '{"corrected_text": "ignored", '
                '"knowledge_tags": ["函数"], '
                '"question_type": "solution", '
                '"difficulty": {"level": 4, "label": "较难", "confidence": 0.72, '
                '"reason": "需要分类讨论。"}}'
            )

        class MetadataChoice:
            message = MetadataMessage()

        class MetadataResponse:
            choices = [MetadataChoice()]

        class MetadataCompletions:
            def create(self, **kwargs):
                return MetadataResponse()

        class MetadataChat:
            completions = MetadataCompletions()

        class MetadataClient:
            chat = MetadataChat()

        service = object.__new__(NLPService)
        service.client = MetadataClient()

        result = service.evaluate_question_metadata("clean text")

        self.assertIs(result["success"], True)
        self.assertEqual(result["question_type"], "solution")
        self.assertEqual(result["difficulty"]["level"], 4)
        self.assertEqual(result["difficulty"]["label"], "较难")

    def test_analyze_invalid_difficulty_falls_back_without_failure(self):
        class InvalidDifficultyMessage:
            content = (
                '{"corrected_text": "clean text", "tags": ["函数"], '
                '"question_type": "fill_blank", '
                '"difficulty": {"level": 9, "label": "超难", "confidence": 2, "reason": "bad"}}'
            )

        class InvalidDifficultyChoice:
            message = InvalidDifficultyMessage()

        class InvalidDifficultyResponse:
            choices = [InvalidDifficultyChoice()]

        class InvalidDifficultyCompletions:
            def create(self, **kwargs):
                return InvalidDifficultyResponse()

        class InvalidDifficultyChat:
            completions = InvalidDifficultyCompletions()

        class InvalidDifficultyClient:
            chat = InvalidDifficultyChat()

        service = object.__new__(NLPService)
        service.client = InvalidDifficultyClient()

        result = service.analyze("OCR text", include_metadata=True)

        self.assertIs(result["success"], True)
        self.assertEqual(result["corrected_text"], "clean text")
        self.assertEqual(result["question_type"], "fill_blank")
        self.assertIsNone(result["difficulty"])
        self.assertEqual(result["metadata_warning"], "difficulty_fallback")


if __name__ == "__main__":
    unittest.main()
