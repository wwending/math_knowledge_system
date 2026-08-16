from __future__ import annotations

import html
import re

from latex2mathml.converter import convert as latex_to_mathml

from app.schemas.paper_render import PaperRenderModel
from app.services.pdf_generation_service import PdfGenerationOptions


MAX_PAPER_ITEMS = 500
MAX_SOURCE_CHARACTERS = 1_000_000
MAX_INLINE_MATH_CHARACTERS = 10_000
MAX_BLOCK_MATH_CHARACTERS = 100_000
MAX_BLOCK_MATH_LINES = 200
DANGEROUS_LATEX_COMMAND = re.compile(
    r"\\(?:href|url|includegraphics|htmlClass|htmlId|htmlStyle|htmlData|require|def|newcommand|input|include)\b",
    re.IGNORECASE,
)


class PaperHtmlRenderError(ValueError):
    pass


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


def render_paper_html(model: PaperRenderModel, options: PdfGenerationOptions) -> str:
    items = [item for section in model.sections for item in section.items]
    source_characters = len(model.paper.title) + len(model.paper.description or "") + sum(
        len(item.content) for item in items
    )
    if len(items) > MAX_PAPER_ITEMS or source_characters > MAX_SOURCE_CHARACTERS:
        raise PaperHtmlRenderError("Paper is too large to render")

    sections_html: list[str] = []
    for section in model.sections:
        item_html: list[str] = []
        for item in section.items:
            score = "" if item.score is None else f'<span class="score">（{_format_number(item.score)} 分）</span>'
            tags = ""
            if item.knowledge_tags:
                tag_html = "".join(f"<span>{html.escape(tag.label)}</span>" for tag in item.knowledge_tags)
                tags = f'<div class="knowledge-tags">{tag_html}</div>'
            answer_lines = ""
            if item.answer_area:
                lines = "".join('<div class="answer-line"></div>' for _ in range(item.answer_area.lines))
                answer_lines = f'<div class="answer-lines">{lines}</div>'
            item_html.append(
                '<article class="question">'
                f'<div class="question-heading"><span>{item.display_number}.</span>{score}</div>'
                f'<div class="question-content">{_render_markdown(item.content)}</div>'
                f"{tags}{answer_lines}</article>"
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
    return f'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src &#x27;none&#x27;; style-src &#x27;unsafe-inline&#x27;; img-src &#x27;none&#x27;; font-src &#x27;none&#x27;; script-src &#x27;none&#x27;; connect-src &#x27;none&#x27;; object-src &#x27;none&#x27;; base-uri &#x27;none&#x27;; form-action &#x27;none&#x27;">
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
.question-content h1, .question-content h2, .question-content h3 {{ font-size: 11.5pt; margin: 2mm 0; break-after: avoid; }}
.question-content pre {{ white-space: pre-wrap; border: 0.2mm solid #d1d5db; padding: 2mm; }}
.question-content math {{ font-size: 1.05em; }}
.math-block {{ margin: 3mm 0; overflow-wrap: anywhere; }}
.math-fallback {{ white-space: pre-wrap; overflow-wrap: anywhere; }}
.score {{ font-weight: 400; }}
.knowledge-tags {{ display: flex; flex-wrap: wrap; gap: 1.5mm; margin-top: 2mm; font-size: 9pt; color: #52616b; }}
.knowledge-tags span {{ border: 0.2mm solid #cbd5df; border-radius: 1mm; padding: 0.5mm 1.5mm; }}
.answer-lines {{ margin-top: 4mm; break-inside: avoid; }}
.answer-line {{ height: 8mm; border-bottom: 0.25mm solid #b8c4cc; }}
</style>
</head>
<body>
<header class="paper-header"><h1>{html.escape(model.paper.title)}</h1>{description}<div class="student-line"><span>姓名：__________</span><span>班级：__________</span><span>日期：__________</span></div></header>
{"".join(sections_html)}
</body>
</html>'''
