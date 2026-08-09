from __future__ import annotations

import re
from typing import Optional

from app.schemas.draft import RecognitionQualityWarning


OPTION_MARKER_PATTERN = re.compile(
    r"(?:^|[\r\n:：;；])[ \t]*(?:[（(][ \t]*([ABCD])[ \t]*[）)]|([ABCD])[ \t]*[.．、）)])[ \t]*",
    re.IGNORECASE,
)
OPTION_SEQUENCE = ("A", "B", "C", "D")


def _effective_length(text: Optional[str]) -> int:
    return len(re.sub(r"\s+", "", text or ""))


def extract_option_markers(text: str) -> list[str]:
    markers = []
    for match in OPTION_MARKER_PATTERN.finditer(text or ""):
        markers.append((match.group(1) or match.group(2)).upper())
    return markers


def detect_option_labels(text: str) -> set[str]:
    return set(extract_option_markers(text))


def is_choice_like(text: str, question_type: Optional[str] = None) -> bool:
    # question_type alone is not enough: this warning requires visible option structure.
    return len(detect_option_labels(text or "")) >= 2


def _has_option_sequence_gap(labels: set[str]) -> bool:
    if len(labels) < 2:
        return False
    indexes = sorted(OPTION_SEQUENCE.index(label) for label in labels if label in OPTION_SEQUENCE)
    if not indexes:
        return False
    expected = set(range(indexes[0], indexes[-1] + 1))
    return set(indexes) != expected


def detect_quality_warnings(
    text: str,
    raw_ocr_text: Optional[str] = None,
    llm_cleaned_text: Optional[str] = None,
    question_type: Optional[str] = None,
) -> list[RecognitionQualityWarning]:
    warnings: list[RecognitionQualityWarning] = []
    safe_text = text or ""
    option_labels = detect_option_labels(safe_text)

    if is_choice_like(safe_text, question_type):
        if len(option_labels) < 4:
            warnings.append(
                RecognitionQualityWarning(
                    code="choice_options_incomplete",
                    message=f"疑似选择题选项不完整：当前只检测到 {len(option_labels)} 个选项，请核对 A/B/C/D 是否齐全。",
                )
            )
        if _has_option_sequence_gap(option_labels):
            warnings.append(
                RecognitionQualityWarning(
                    code="choice_options_sequence_gap",
                    message="疑似选择题选项顺序异常：检测到选项标签不连续，请核对是否存在 OCR 漏识别或双栏选项错排。",
                )
            )

    if _effective_length(safe_text) < 15:
        warnings.append(
            RecognitionQualityWarning(
                code="recognized_text_too_short",
                message="识别文本较短，可能存在漏识别，请核对原图和原始 OCR 文本。",
            )
        )

    raw_len = _effective_length(raw_ocr_text)
    cleaned_len = _effective_length(llm_cleaned_text)
    if raw_len > 40 and cleaned_len > 0 and cleaned_len < raw_len * 0.6:
        warnings.append(
            RecognitionQualityWarning(
                code="ocr_llm_text_changed_substantially",
                message="LLM 清洗后文本明显变短，请核对是否删除了题干或选项内容。",
            )
        )

    return warnings
