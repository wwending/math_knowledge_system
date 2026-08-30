from __future__ import annotations

import base64
import html
import re
from typing import Callable, Optional

from latex2mathml.converter import convert as latex_to_mathml

from app.schemas.paper_render import PaperRenderItem, PaperRenderModel
from app.services.pdf_generation_service import PdfGenerationOptions


MAX_PAPER_ITEMS = 500
MAX_SOURCE_CHARACTERS = 1_000_000
MAX_INLINE_MATH_CHARACTERS = 10_000
MAX_BLOCK_MATH_CHARACTERS = 100_000
MAX_BLOCK_MATH_LINES = 200
# Figure embed limits (#59): an oversized figure fails the render loudly instead
# of silently dropping it. Raw-byte caps keep the base64-inflated single-file
# HTML comfortably inside what Gotenberg's Chromium converts within the read
# timeout.
MAX_FIGURE_EMBED_BYTES = 4 * 1024 * 1024
MAX_TOTAL_FIGURE_EMBED_BYTES = 24 * 1024 * 1024
ALLOWED_FIGURE_MIME_TYPES = {"image/jpeg", "image/png"}
FigureLoader = Callable[[PaperRenderItem, Optional[str]], Optional[tuple[bytes, Optional[str]]]]
DANGEROUS_LATEX_COMMAND = re.compile(
    r"\\(?:href|url|includegraphics|htmlClass|htmlId|htmlStyle|htmlData|require|def|newcommand|input|include)\b",
    re.IGNORECASE,
)


class PaperHtmlRenderError(ValueError):
    pass


class PaperFigureTooLargeError(PaperHtmlRenderError):
    """A question figure exceeds the embed limits; its message names the question."""



def _is_escaped(source: str, position: int) -> bool:
    backslashes = 0
    for index in range(position - 1, -1, -1):
        if source[index] != "\\":
            break
        backslashes += 1
    return backslashes % 2 == 1


def _normalize_latex_delimiters(source: str) -> str:
    return source.replace("\\[", "$$").replace("\\]", "$$").replace("\\(", "$").replace("\\)", "$")


def _safe_math(expression: str, *, display: bool) -> str:
    character_limit = MAX_BLOCK_MATH_CHARACTERS if display else MAX_INLINE_MATH_CHARACTERS
    line_limit_exceeded = display and expression.count("\n") + 1 > MAX_BLOCK_MATH_LINES
    if (
        not expression.strip()
        or len(expression) > character_limit
        or line_limit_exceeded
        or DANGEROUS_LATEX_COMMAND.search(expression)
    ):
        return f'<code class="math-fallback">{html.escape(expression)}</code>'
    try:
        rendered = latex_to_mathml(expression, display="block" if display else "inline")
    except Exception:
        return f'<code class="math-fallback">{html.escape(expression)}</code>'
    if re.search(r"<(?:script|style|img|iframe|object|embed)\b|\b(?:href|src|style|on\w+)\s*=", rendered, re.IGNORECASE):
        return f'<code class="math-fallback">{html.escape(expression)}</code>'
    return rendered


def _render_plain_inline(source: str) -> str:
    escaped = html.escape(source)
    escaped = re.sub(r"\*\*([^*\n]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", escaped)
    return escaped


def _render_math_inline(source: str) -> str:
    result: list[str] = []
    text_start = 0
    cursor = 0
    while cursor < len(source):
        if source[cursor] != "$" or _is_escaped(source, cursor):
            cursor += 1
            continue
        if cursor + 1 < len(source) and source[cursor + 1] == "$":
            cursor += 2
            continue
        closing = cursor + 1
        while closing < len(source):
            if source[closing] == "\n":
                closing = -1
                break
            if source[closing] == "$" and not _is_escaped(source, closing):
                break
            if closing - cursor > MAX_INLINE_MATH_CHARACTERS:
                closing = -1
                break
            closing += 1
        if closing < 0 or closing >= len(source):
            cursor += 1
            continue
        result.append(_render_plain_inline(source[text_start:cursor]))
        result.append(_safe_math(source[cursor + 1 : closing], display=False))
        cursor = closing + 1
        text_start = cursor
    result.append(_render_plain_inline(source[text_start:]))
    return "".join(result)


def _render_inline(source: str) -> str:
    result: list[str] = []
    cursor = 0
    for code_match in re.finditer(r"`([^`\n]+)`", source):
        result.append(_render_math_inline(source[cursor : code_match.start()]))
        result.append(f"<code>{html.escape(code_match.group(1))}</code>")
        cursor = code_match.end()
    result.append(_render_math_inline(source[cursor:]))
    return "".join(result)


def _render_markdown(source: str) -> str:
    source = _normalize_latex_delimiters(source or "")
    lines = source.splitlines()
    output: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    list_tag: str | None = None
    index = 0

    def flush_paragraph() -> None:
        if paragraph:
            output.append(f"<p>{'<br>'.join(_render_inline(line) for line in paragraph)}</p>")
            paragraph.clear()

    def flush_list() -> None:
        nonlocal list_tag
        if list_tag:
            output.append(f"<{list_tag}>{''.join(list_items)}</{list_tag}>")
            list_items.clear()
            list_tag = None

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_paragraph()
            flush_list()
            code_lines: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index])
                index += 1
            output.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
        elif stripped.startswith("$$"):
            flush_paragraph()
            flush_list()
            expression_parts = [stripped[2:]]
            while not expression_parts[-1].rstrip().endswith("$$") and index + 1 < len(lines):
                index += 1
                expression_parts.append(lines[index])
                if len(expression_parts) > MAX_BLOCK_MATH_LINES:
                    break
            expression = "\n".join(expression_parts)
            if expression.rstrip().endswith("$$"):
                expression = expression.rstrip()[:-2]
            output.append(f'<div class="math-block">{_safe_math(expression, display=True)}</div>')
        elif not stripped:
            flush_paragraph()
            flush_list()
        else:
            heading = re.match(r"^(#{1,3})\s+(.+)$", stripped)
            unordered = re.match(r"^[-*+]\s+(.+)$", stripped)
            ordered = re.match(r"^\d+[.)]\s+(.+)$", stripped)
            if heading:
                flush_paragraph()
                flush_list()
                level = len(heading.group(1))
                output.append(f"<h{level}>{_render_inline(heading.group(2))}</h{level}>")
            elif unordered or ordered:
                flush_paragraph()
                requested_tag = "ul" if unordered else "ol"
                if list_tag and list_tag != requested_tag:
                    flush_list()
                list_tag = requested_tag
                list_items.append(f"<li>{_render_inline((unordered or ordered).group(1))}</li>")
            else:
                flush_list()
                paragraph.append(line)
        index += 1

    flush_paragraph()
    flush_list()
    return "\n".join(output)


def _format_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def render_paper_html(
    model: PaperRenderModel,
    options: PdfGenerationOptions,
    *,
    figure_loader: Optional[FigureLoader] = None,
) -> str:
    items = [item for section in model.sections for item in section.items]
    source_characters = len(model.paper.title) + len(model.paper.description or "") + sum(
        len(item.content) + len(item.answer or "") + len(item.analysis or "") for item in items
    )
    if len(items) > MAX_PAPER_ITEMS or source_characters > MAX_SOURCE_CHARACTERS:
        raise PaperHtmlRenderError("Paper is too large to render")

    sections_html: list[str] = []
    embedded_any_figure = False
    embedded_figure_bytes = 0

    def embed_figure(item: PaperRenderItem, figure_id: Optional[str], alt_text: str) -> str:
        nonlocal embedded_any_figure, embedded_figure_bytes
        if figure_loader is None:
            raise PaperHtmlRenderError(f"第 {item.display_number} 题快照图片不可读")
        try:
            source = figure_loader(item, figure_id)
        except TypeError:
            # Compatibility for callers of the legacy single-image renderer.
            source = figure_loader(item)  # type: ignore[call-arg]
        if source is None:
            raise PaperHtmlRenderError(f"第 {item.display_number} 题快照图片 {figure_id or 'legacy'} 不可读")
        figure_bytes, figure_mime = source
        if figure_mime not in ALLOWED_FIGURE_MIME_TYPES:
            raise PaperHtmlRenderError(f"第 {item.display_number} 题快照图片格式不受支持")
        if len(figure_bytes) > MAX_FIGURE_EMBED_BYTES:
            raise PaperFigureTooLargeError(f"第 {item.display_number} 题配图过大，无法嵌入试卷")
        embedded_figure_bytes += len(figure_bytes)
        if embedded_figure_bytes > MAX_TOTAL_FIGURE_EMBED_BYTES:
            raise PaperFigureTooLargeError(
                f"试卷配图总体积超出嵌入上限（累计到第 {item.display_number} 题时超限）"
            )
        embedded_any_figure = True
        encoded = base64.b64encode(figure_bytes).decode("ascii")
        return f'<img src="data:{figure_mime};base64,{encoded}" alt="{html.escape(alt_text)}">'

    def render_document_section(item: PaperRenderItem, section_name: str) -> str:
        snapshot = item.section_snapshot or {}
        blocks = snapshot.get("sections", {}).get(section_name, {}).get("blocks", [])
        if not blocks:
            legacy = {"stem": item.content, "answer": item.answer, "analysis": item.analysis}[section_name]
            return _render_markdown(legacy or "")
        rendered: list[str] = []
        content_width = options.page_width_mm - options.margin_left_mm - options.margin_right_mm
        content_height = options.page_height_mm - options.margin_top_mm - options.margin_bottom_mm
        for block in blocks:
            if block.get("kind") == "text":
                rendered.append(f'<div class="document-text">{_render_markdown(block.get("markdown") or "")}</div>')
                continue
            ratio = float(block.get("height_ratio") or 0)
            if ratio * content_width > content_height:
                raise PaperHtmlRenderError(f"第 {item.display_number} 题图片区超过可打印内容高度")
            placements: list[str] = []
            for index, placement in enumerate(block.get("placements") or []):
                figure_id = str(placement.get("figure_id"))
                image = embed_figure(item, figure_id, f"第{item.display_number}题配图{index + 1}")
                style = ";".join(
                    f"{name}:{float(placement[key]) * 100:g}%"
                    for name, key in (("left", "x"), ("top", "y"), ("width", "width"), ("height", "height"))
                )
                placements.append(f'<span class="image-placement" style="{style}">{image}</span>')
            rendered.append(
                f'<div class="image-area" style="aspect-ratio:1/{ratio:g}">{"".join(placements)}</div>'
            )
        return "".join(rendered)

    def section_has_content(item: PaperRenderItem, section_name: str) -> bool:
        blocks = (item.section_snapshot or {}).get("sections", {}).get(section_name, {}).get("blocks", [])
        return bool(blocks) if item.section_snapshot else bool({"answer": item.answer, "analysis": item.analysis}.get(section_name))
    for section in model.sections:
        item_html: list[str] = []
        for item in section.items:
            score = "" if item.score is None else f'<span class="score">（{_format_number(item.score)} 分）</span>'
            tags = ""
            if item.knowledge_tags:
                tag_html = "".join(f"<span>{html.escape(tag.label)}</span>" for tag in item.knowledge_tags)
                tags = f'<div class="knowledge-tags">{tag_html}</div>'
            question_tail = ""
            if item.answer_area:
                answer_area = (
                    f'<div class="answer-area" style="height: {item.answer_area.height_mm:g}mm"></div>'
                )
                question_tail = f'<div class="question-tail">{tags}{answer_area}</div>'
            figure_html = ""
            if not item.section_snapshot and item.figure_image_url:
                figure_html = f'<div class="question-figure">{embed_figure(item, None, f"第{item.display_number}题配图")}</div>'
            answer_html = (
                f'<section class="answer-section"><h3>答案</h3>{render_document_section(item, "answer")}</section>'
                if model.layout.show_answers and section_has_content(item, "answer") else ""
            )
            analysis_html = (
                f'<section class="analysis-section"><h3>解析</h3>{render_document_section(item, "analysis")}</section>'
                if model.layout.show_analysis and section_has_content(item, "analysis") else ""
            )
            item_html.append(
                '<article class="question">'
                f'<div class="question-heading"><span>{item.display_number}.</span>{score}</div>'
                f'<div class="question-content">{render_document_section(item, "stem")}</div>'
                f"{figure_html}"
                f"{answer_html}{analysis_html}"
                f"{question_tail or tags}</article>"
            )
        sections_html.append(
            f'<section class="paper-section"><h2>{html.escape(section.title)}</h2>{"".join(item_html)}</section>'
        )

    description = (
        f'<p class="description">{html.escape(model.paper.description)}</p>'
        if model.paper.description
        else ""
    )
    page_size = f"{options.page_width_mm:g}mm {options.page_height_mm:g}mm"
    margins = (
        f"{options.margin_top_mm:g}mm {options.margin_right_mm:g}mm "
        f"{options.margin_bottom_mm:g}mm {options.margin_left_mm:g}mm"
    )
    # Papers without figures keep the exact pre-#59 markup byte for byte: the
    # data: relaxation and the figure CSS only appear when a figure was embedded.
    img_src_directive = "data:" if embedded_any_figure else "&#x27;none&#x27;"
    figure_css = (
        "\n.question-figure { margin-top: 2mm; break-inside: avoid; page-break-inside: avoid; }\n.question-figure img { display:block; max-width:100%; height:auto; }\n.image-area { position:relative; width:100%; overflow:hidden; break-inside:avoid; page-break-inside:avoid; }\n.image-placement { position:absolute; display:block; }\n.image-placement img { display:block; width:100%; height:100%; object-fit:fill; }"
        if embedded_any_figure
        else ""
    )
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src &#x27;none&#x27;; style-src &#x27;unsafe-inline&#x27;; img-src {img_src_directive}; font-src &#x27;none&#x27;; script-src &#x27;none&#x27;; connect-src &#x27;none&#x27;; object-src &#x27;none&#x27;; base-uri &#x27;none&#x27;; form-action &#x27;none&#x27;">
<title>{html.escape(model.paper.title)}</title>
<style>
@page {{ size: {page_size}; margin: {margins}; }}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; color: #1f2933; background: #fff; }}
body {{ font-family: "Noto Sans CJK SC", "Microsoft YaHei", "PingFang SC", sans-serif; font-size: 11pt; line-height: 1.65; }}
.paper-header {{ text-align: center; border-bottom: 0.3mm solid #cbd5df; padding-bottom: 5mm; margin-bottom: 7mm; }}
h1 {{ margin: 0 0 2.5mm; font-size: 20pt; line-height: 1.3; }}
.description {{ margin: 0 0 4mm; color: #52616b; }}
.student-line {{ display: flex; justify-content: center; gap: 10mm; font-size: 10.5pt; }}
.paper-section {{ margin-top: 7mm; }}
.paper-section > h2 {{ margin: 0 0 4mm; padding-left: 3mm; border-left: 1.2mm solid #3b82b8; font-size: 14pt; break-after: avoid; }}
.question {{ margin-bottom: 6mm; }}
.question-heading {{ display: flex; gap: 1.5mm; font-weight: 700; margin-bottom: 2mm; break-after: avoid; }}
.question-content p {{ margin: 0 0 2.5mm; }}
.question-content > :last-child {{ break-after: avoid; page-break-after: avoid; }}
.question-content h1, .question-content h2, .question-content h3 {{ font-size: 11.5pt; margin: 2mm 0; break-after: avoid; }}
.question-content pre {{ white-space: pre-wrap; border: 0.2mm solid #d1d5db; padding: 2mm; }}
.question-content math {{ font-size: 1.05em; }}
.answer-section, .analysis-section {{ margin-top: 3mm; }}
.answer-section h3, .analysis-section h3 {{ margin: 0 0 1.5mm; font-size: 11pt; }}
.math-block {{ margin: 3mm 0; overflow-wrap: anywhere; }}
.math-fallback {{ white-space: pre-wrap; overflow-wrap: anywhere; }}
.score {{ font-weight: 400; }}
.knowledge-tags {{ display: flex; flex-wrap: wrap; gap: 1.5mm; margin-top: 2mm; font-size: 9pt; color: #52616b; }}
.knowledge-tags span {{ border: 0.2mm solid #cbd5df; border-radius: 1mm; padding: 0.5mm 1.5mm; }}
.question-tail {{ break-before: avoid; page-break-before: avoid; break-inside: avoid; page-break-inside: avoid; }}
.answer-area {{ margin-top: 4mm; break-inside: avoid; page-break-inside: avoid; background: #fff; }}{figure_css}
</style>
</head>
<body>
<header class="paper-header"><h1>{html.escape(model.paper.title)}</h1>{description}<div class="student-line"><span>姓名：__________</span><span>班级：__________</span><span>日期：__________</span></div></header>
{"".join(sections_html)}
</body>
</html>'''
