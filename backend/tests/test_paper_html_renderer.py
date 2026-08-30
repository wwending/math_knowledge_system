import base64
import unittest
import re
from unittest.mock import patch

from app.schemas.paper_render import (
    PaperRenderAnswerArea,
    PaperRenderItem,
    PaperRenderLayout,
    PaperRenderModel,
    PaperRenderPaperMeta,
    PaperRenderSection,
)
from app.services import paper_html_renderer
from app.services.paper_html_renderer import render_paper_html
from app.services.pdf_generation_service import PdfGenerationOptions


def _render_model(content: str, *, with_answer_area: bool = True) -> PaperRenderModel:
    return PaperRenderModel(
        template_type="homework",
        version="student",
        paper_size="A4",
        group_by="question_type",
        sort_by="position",
        answer_area_mode="after_each_question" if with_answer_area else "none",
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
                        answer_area=(
                            PaperRenderAnswerArea(mode="after_each_question", response_line_count=6, height_mm=48)
                            if with_answer_area
                            else None
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
        self.assertEqual(first.count('class="answer-area"'), 1)
        self.assertIn('class="answer-area" style="height: 48mm"', first)
        self.assertNotIn('class="answer-line"', first)
        self.assertNotIn("border-bottom: 0.25mm solid #b8c4cc", first)
        self.assertIn(".question-content > :last-child { break-after: avoid;", first)
        self.assertIn(".question-tail { break-before: avoid;", first)
        self.assertNotIn(".question { margin-bottom: 6mm; break-inside: avoid;", first)

    def test_none_mode_does_not_render_an_answer_area(self):
        html = render_paper_html(
            _render_model("无需答题区", with_answer_area=False),
            PdfGenerationOptions.a4_portrait(),
        )

        self.assertNotIn('class="answer-area"', html)
        self.assertNotIn('class="question-tail"', html)

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


class PaperFigureEmbeddingTests(unittest.TestCase):
    JPEG_FIGURE = b"fake-jpeg-bytes"

    def _figured_model(self) -> PaperRenderModel:
        model = _render_model("如图所示")
        item = model.sections[0].items[0]
        model.sections[0].items[0] = item.model_copy(
            update={"figure_image_url": "/api/v1/papers/7/items/11/image"}
        )
        return model

    @staticmethod
    def _loader(payload=None, mime="image/jpeg"):
        def load(item):
            if payload is None:
                return None
            return payload, mime

        return load

    def test_embeds_data_uri_and_relaxes_csp_and_css(self):
        html = render_paper_html(
            self._figured_model(),
            PdfGenerationOptions.a4_portrait(),
            figure_loader=self._loader(self.JPEG_FIGURE),
        )

        encoded = base64.b64encode(self.JPEG_FIGURE).decode()
        self.assertIn(f"data:image/jpeg;base64,{encoded}", html)
        self.assertIn('class="question-figure"', html)
        self.assertIn('alt="第1题配图"', html)
        self.assertIn("img-src data:", html)
        self.assertNotIn("img-src &#x27;none&#x27;", html)
        self.assertIn(".question-figure img { display:block; max-width:100%", html)

    def test_figure_lands_between_content_and_tail(self):
        html = render_paper_html(
            self._figured_model(),
            PdfGenerationOptions.a4_portrait(),
            figure_loader=self._loader(self.JPEG_FIGURE),
        )

        content_at = html.index('class="question-content"')
        figure_at = html.index('class="question-figure"')
        tail_at = html.index('class="answer-area"')
        self.assertTrue(content_at < figure_at < tail_at)

    def test_no_figure_output_stays_byte_identical_to_legacy_markup(self):
        options = PdfGenerationOptions.a4_portrait()
        legacy = render_paper_html(_render_model("无图"), options)

        self.assertIn("img-src &#x27;none&#x27;", legacy)
        self.assertNotIn("<img", legacy.lower())
        self.assertNotIn(".question-figure", legacy)
        # Deterministic double render (existing contract) plus explicit
        # absence of every #59 marker above is the byte-identity evidence.

    def test_declared_figure_without_readable_bytes_fails(self):
        options = PdfGenerationOptions.a4_portrait()

        with self.assertRaises(paper_html_renderer.PaperHtmlRenderError):
            render_paper_html(self._figured_model(), options)
        with self.assertRaises(paper_html_renderer.PaperHtmlRenderError):
            render_paper_html(self._figured_model(), options, figure_loader=self._loader(None))
        plain = render_paper_html(_render_model("无图"), options, figure_loader=self._loader(b"x"))

        self.assertNotIn("<img", plain.lower())
        self.assertIn("img-src &#x27;none&#x27;", plain)

    def test_non_whitelisted_mime_fails(self):
        with self.assertRaises(paper_html_renderer.PaperHtmlRenderError):
            render_paper_html(
                self._figured_model(),
                PdfGenerationOptions.a4_portrait(),
                figure_loader=self._loader(self.JPEG_FIGURE, mime="image/svg+xml"),
            )

    def test_oversized_single_figure_raises_with_display_number(self):
        with patch.object(paper_html_renderer, "MAX_FIGURE_EMBED_BYTES", 8):
            with self.assertRaises(paper_html_renderer.PaperFigureTooLargeError) as ctx:
                render_paper_html(
                    self._figured_model(),
                    PdfGenerationOptions.a4_portrait(),
                    figure_loader=self._loader(b"123456789"),
                )

        self.assertIn("第 1 题", str(ctx.exception))

    def test_total_budget_exhaustion_raises_naming_current_question(self):
        small_items_model = self._figured_model()
        extra = PaperRenderItem(
            paper_item_id=12,
            question_id=18,
            position=2,
            display_number=2,
            score=5,
            content="第二题",
            question_type="solution",
            question_type_label="解答题",
            knowledge_tags=[],
            answer_area=None,
            figure_image_url="/api/v1/papers/7/items/12/image",
        )
        small_items_model.sections[0].items.append(extra)
        budget = {"spent": 0}

        def loader(item):
            budget["spent"] += 6
            return b"123456", "image/jpeg"

        with patch.object(paper_html_renderer, "MAX_TOTAL_FIGURE_EMBED_BYTES", 10):
            with self.assertRaises(paper_html_renderer.PaperFigureTooLargeError) as ctx:
                render_paper_html(
                    small_items_model,
                    PdfGenerationOptions.a4_portrait(),
                    figure_loader=loader,
                )

        self.assertIn("第 2 题", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
