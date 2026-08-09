import unittest
import re

from app.schemas.paper_render import (
    PaperRenderAnswerArea,
    PaperRenderItem,
    PaperRenderLayout,
    PaperRenderModel,
    PaperRenderPaperMeta,
    PaperRenderSection,
)
from app.services.paper_html_renderer import render_paper_html
from app.services.pdf_generation_service import PdfGenerationOptions


def _render_model(content: str) -> PaperRenderModel:
    return PaperRenderModel(
        template_type="homework",
        version="student",
        paper_size="A4",
        group_by="question_type",
        sort_by="position",
        answer_area_mode="after_each_question",
        paper=PaperRenderPaperMeta(
            id=7,
            title='中文试卷 <script>alert("title")</script>',
            description="Markdown 与数学公式回归",
            status="draft",
            item_count=1,
            total_score=10,
        ),
        layout=PaperRenderLayout(),
        sections=[
            PaperRenderSection(
                key="solution",
                title="解答题",
                items=[
                    PaperRenderItem(
                        paper_item_id=11,
                        question_id=17,
                        position=1,
                        display_number=1,
                        score=10,
                        content=content,
                        question_type="solution",
                        question_type_label="解答题",
                        knowledge_tags=[],
                        answer_area=PaperRenderAnswerArea(
                            mode="after_each_question",
                            lines=4,
                        ),
                    )
                ],
            )
        ],
    )


class PaperHtmlRendererTests(unittest.TestCase):
    def test_renders_a4_paper_content_math_and_answer_area_deterministically(self):
        model = _render_model("**求解**：$x^2 + y^2 = 1$")
        options = PdfGenerationOptions.a4_portrait()

        first = render_paper_html(model, options)
        second = render_paper_html(model, options)

        self.assertEqual(first, second)
        self.assertIn('<meta charset="utf-8">', first)
        self.assertIn("size: 210mm 297mm", first)
        self.assertIn("margin: 18mm 16mm 18mm 16mm", first)
        self.assertIn("中文试卷", first)
        self.assertIn("解答题", first)
        self.assertIn("1.", first)
        self.assertIn("10 分", first)
        self.assertIn("<strong>求解</strong>", first)
        self.assertIn("<math", first)
        self.assertEqual(first.count('class="answer-line"'), 4)

    def test_escapes_html_and_never_emits_remote_or_executable_resources(self):
        html = render_paper_html(
            _render_model(
                '<img src="https://attacker.example/x" onerror="alert(1)">\n'
                '[remote](https://attacker.example/)\n'
                '$\\includegraphics{https://attacker.example/math.png}$'
            ),
            PdfGenerationOptions.a4_portrait(),
        )

        self.assertNotIn("<script", html.lower())
        self.assertNotIn("<img", html.lower())
        self.assertIsNone(re.search(r"<[^>]+\sonerror\s*=", html, re.IGNORECASE))
        self.assertNotIn('href="http', html.lower())
        self.assertNotIn('src="http', html.lower())
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&lt;img", html)
        self.assertIn("Content-Security-Policy", html)
        self.assertIn("default-src &#x27;none&#x27;", html)

    def test_keeps_math_inside_code_literal_and_renders_common_display_math(self):
        html = render_paper_html(
            _render_model("代码：`$not_math$`\n\n$$\\frac{-b\\pm\\sqrt{b^2-4ac}}{2a}$$"),
            PdfGenerationOptions.a4_portrait(),
        )

        self.assertIn("<code>$not_math$</code>", html)
        self.assertIn('display="block"', html)
        self.assertIn("<mfrac>", html)


if __name__ == "__main__":
    unittest.main()
