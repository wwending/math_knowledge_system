import unittest

from app.services.llm import NLPService, _summarize_deepseek_response, normalize_latex_delimiters


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


class CustomCompletions:
    def __init__(self, response):
        self.response = response
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return self.response


class CustomChat:
    def __init__(self, response):
        self.completions = CustomCompletions(response)


class CustomClient:
    def __init__(self, response):
        self.chat = CustomChat(response)

    @property
    def last_create_kwargs(self):
        return self.chat.completions.last_kwargs


class CustomMessage:
    def __init__(self, content=None, role="assistant", refusal=None, reasoning_content=None, tool_calls=None):
        self.content = content
        self.role = role
        self.refusal = refusal
        self.reasoning_content = reasoning_content
        self.tool_calls = tool_calls


class CustomChoice:
    def __init__(self, message=None, finish_reason="stop"):
        self.message = message
        self.finish_reason = finish_reason


class CustomUsage:
    prompt_tokens = 11
    completion_tokens = 22
    total_tokens = 33


class CustomResponse:
    def __init__(self, choices=None, response_id="resp_test", model="deepseek-test", created=123456):
        self.id = response_id
        self.model = model
        self.created = created
        self.choices = choices
        self.usage = CustomUsage()


class NoChoicesResponse:
    id = "resp_no_choices"
    model = "deepseek-test"
    created = 123456
    usage = CustomUsage()


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

    def test_analyze_passes_thinking_disabled_and_json_object_response_format(self):
        response = CustomResponse(
            choices=[
                CustomChoice(
                    CustomMessage(
                        content='{"corrected_text": "clean text", "knowledge_tags": ["函数"]}',
                    )
                )
            ]
        )
        client = CustomClient(response)
        service = object.__new__(NLPService)
        service.client = client

        result = service.analyze("OCR text")

        self.assertIs(result["success"], True)
        kwargs = client.last_create_kwargs
        self.assertEqual(kwargs["extra_body"], {"thinking": {"type": "disabled"}})
        self.assertEqual(kwargs["response_format"], {"type": "json_object"})
        self.assertEqual(kwargs["max_tokens"], 2048)
        self.assertEqual(kwargs["timeout"], 45)
        self.assertNotIn("reasoning_effort", kwargs)

    def test_analyze_prompt_requires_json_and_includes_output_example(self):
        response = CustomResponse(
            choices=[
                CustomChoice(
                    CustomMessage(
                        content='{"corrected_text": "clean text", "knowledge_tags": ["函数"]}',
                    )
                )
            ]
        )
        client = CustomClient(response)
        service = object.__new__(NLPService)
        service.client = client

        result = service.analyze("OCR text")

        self.assertIs(result["success"], True)
        kwargs = client.last_create_kwargs
        system_prompt = kwargs["messages"][0]["content"]
        user_prompt = kwargs["messages"][1]["content"]
        combined_prompt = f"{system_prompt}\n{user_prompt}".lower()
        self.assertIn("json", combined_prompt)
        self.assertIn('"corrected_text"', user_prompt)
        self.assertIn('"knowledge_tags"', user_prompt)
        self.assertIn("高中数学 OCR 文本清洗与结构化工具", system_prompt)
        self.assertIn("不解题", system_prompt)
        self.assertIn("不证明", system_prompt)
        self.assertIn("不分析", system_prompt)
        self.assertIn("不输出推理过程", system_prompt)
        self.assertIn("不改变题意", combined_prompt)
        self.assertIn("不得根据常见题型猜测原题", combined_prompt)
        self.assertIn("不得删除选项", combined_prompt)
        self.assertIn("AF1", user_prompt)
        self.assertIn("AF2", user_prompt)

    def test_analyze_handles_empty_choices_with_invalid_response_detail(self):
        service = object.__new__(NLPService)
        service.client = CustomClient(CustomResponse(choices=[]))

        result = service.analyze("OCR text")

        self.assertIs(result["success"], False)
        self.assertEqual(result["error_type"], "invalid_response")
        self.assertIn("deepseek_invalid_choice_shape", result["detail"])
        self.assertIn("choices_count=0", result["detail"])
        self.assertEqual(result["corrected_text"], "OCR text")

    def test_analyze_handles_response_without_choices(self):
        service = object.__new__(NLPService)
        service.client = CustomClient(NoChoicesResponse())

        result = service.analyze("OCR text")

        self.assertIs(result["success"], False)
        self.assertEqual(result["error_type"], "invalid_response")
        self.assertIn("deepseek_invalid_choice_shape", result["detail"])
        self.assertIn("choices_count=0", result["detail"])

    def test_analyze_handles_empty_message_content_with_diagnostic_detail(self):
        response = CustomResponse(choices=[CustomChoice(CustomMessage(content=""), finish_reason="length")])
        service = object.__new__(NLPService)
        service.client = CustomClient(response)

        result = service.analyze("OCR text")

        self.assertIs(result["success"], False)
        self.assertEqual(result["error_type"], "invalid_response")
        self.assertIn("deepseek_length_exhausted_empty_content", result["detail"])
        self.assertIn("choices_count=1", result["detail"])
        self.assertIn("finish_reason=length", result["detail"])
        self.assertIn("content_len=0", result["detail"])
        self.assertIn("completion_tokens=22", result["detail"])

    def test_analyze_handles_whitespace_message_content_as_empty(self):
        response = CustomResponse(choices=[CustomChoice(CustomMessage(content="   \n\t  "), finish_reason="stop")])
        service = object.__new__(NLPService)
        service.client = CustomClient(response)

        result = service.analyze("OCR text")

        self.assertIs(result["success"], False)
        self.assertEqual(result["error_type"], "invalid_response")
        self.assertIn("deepseek_empty_content", result["detail"])
        self.assertIn("content_len=7", result["detail"])

    def test_analyze_handles_non_json_content_without_echoing_full_content(self):
        long_content = "not-json-" + ("x" * 500)
        response = CustomResponse(choices=[CustomChoice(CustomMessage(content=long_content), finish_reason="stop")])
        service = object.__new__(NLPService)
        service.client = CustomClient(response)

        result = service.analyze("OCR text")

        self.assertIs(result["success"], False)
        self.assertEqual(result["error_type"], "invalid_response")
        self.assertIn("deepseek_non_json", result["detail"])
        self.assertNotIn("x" * 300, result["detail"])

    def test_analyze_rejects_json_missing_corrected_text(self):
        response = CustomResponse(choices=[CustomChoice(CustomMessage(content='{"knowledge_tags": ["函数"]}'))])
        service = object.__new__(NLPService)
        service.client = CustomClient(response)

        result = service.analyze("OCR text")

        self.assertIs(result["success"], False)
        self.assertEqual(result["error_type"], "invalid_response")
        self.assertIn("deepseek_missing_corrected_text", result["detail"])

    def test_summarize_deepseek_response_truncates_raw_and_message_fields(self):
        long_content = "公式" + ("x" * 500)
        long_refusal = "拒绝" + ("y" * 500)
        long_reasoning = "推理" + ("z" * 500)
        response = CustomResponse(
            choices=[
                CustomChoice(
                    CustomMessage(
                        content=long_content,
                        refusal=long_refusal,
                        reasoning_content=long_reasoning,
                        tool_calls=[{"name": "tool"}],
                    ),
                    finish_reason="stop",
                )
            ]
        )

        summary = _summarize_deepseek_response(
            response,
            input_text_len=123,
            configured_model="deepseek-chat",
            timeout_seconds=30,
        )

        self.assertEqual(summary["choices_count"], 1)
        self.assertEqual(summary["content_len"], len(long_content))
        self.assertTrue(summary["has_refusal"])
        self.assertTrue(summary["has_reasoning_content"])
        self.assertTrue(summary["has_tool_calls"])
        self.assertEqual(summary["usage_completion_tokens"], 22)
        self.assertEqual(summary["input_text_len"], 123)
        self.assertEqual(summary["configured_model"], "deepseek-chat")
        self.assertEqual(summary["timeout_seconds"], 30)
        self.assertLessEqual(len(summary["content_preview"]), 200)
        self.assertLessEqual(len(summary["refusal_preview"]), 200)
        self.assertLessEqual(len(summary["reasoning_content_preview"]), 200)
        self.assertLessEqual(len(summary["raw_response_preview"]), 1000)
        self.assertNotIn("x" * 300, str(summary))
        self.assertNotIn("y" * 300, str(summary))
        self.assertNotIn("z" * 300, str(summary))

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
