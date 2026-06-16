from __future__ import annotations

import re
from typing import Optional

from app.schemas.draft import RecognitionQualityWarning


OPTION_LABEL_PATTERN = re.compile(r"(?<![A-Za-z0-9])([ABCD])(?:[.．、）)]|\s+)", re.IGNORECASE)
CHOICE_BLANK_PATTERNS = ("（ ）", "( )", "()", "（）")
CHOICE_TYPES = {"choice", "single_choice", "multiple_choice"}
OPTION_SEQUENCE = ("A", "B", "C", "D")


def _effective_length(text: Optional[str]) -> int:
    return len(re.sub(r"\s+", "", text or ""))


def detect_option_labels(text: str) -> set[str]:
    return {match.group(1).upper() for match in OPTION_LABEL_PATTERN.finditer(text or "")}


def is_choice_like(text: str, question_type: Optional[str] = None) -> bool:
    normalized_type = (question_type or "").strip().lower()
    if normalized_type in CHOICE_TYPES:
        return True
    if any(pattern in (text or "") for pattern in CHOICE_BLANK_PATTERNS):
        return True
    return bool(detect_option_labels(text or ""))


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
