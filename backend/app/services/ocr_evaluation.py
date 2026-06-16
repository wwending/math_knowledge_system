from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any


@dataclass(frozen=True)
class OcrEvalMetrics:
    exact_match: bool
    normalized_exact_match: bool
    similarity_ratio: float
    length_delta: int
    required_terms_total: int
    required_terms_hit: int
    required_terms_recall: float
    error: str | None = None


@dataclass(frozen=True)
class OcrEvalRecord:
    case_id: str
    provider: str
    metrics: OcrEvalMetrics
    latency_ms: int | None = None


@dataclass(frozen=True)
class OcrProviderEvalSummary:
    provider: str
    total_predictions: int
    exact_matches: int
    normalized_exact_matches: int
    avg_similarity_ratio: float
    avg_required_terms_recall: float
    error_count: int
    avg_latency_ms: float | None


@dataclass(frozen=True)
class OcrEvalSummary:
    total_cases: int
    total_predictions: int
    evaluated_count: int
    missing_predictions_count: int
    error_predictions_count: int
    by_provider: dict[str, OcrProviderEvalSummary]
    records: list[OcrEvalRecord]


def normalize_ocr_text(text: str) -> str:
    return " ".join(str(text or "").split())


def evaluate_ocr_prediction(
    expected_text: str,
    predicted_text: str,
    required_terms: list[str] | None = None,
    error: str | None = None,
) -> OcrEvalMetrics:
    expected = str(expected_text or "")
    predicted = str(predicted_text or "")
    normalized_expected = normalize_ocr_text(expected)
    normalized_predicted = normalize_ocr_text(predicted)
    terms = required_terms or []
    normalized_terms = [normalize_ocr_text(term) for term in terms]

    required_terms_hit = sum(
        1 for term in normalized_terms if term and term in normalized_predicted
    )
    required_terms_total = len(normalized_terms)
    required_terms_recall = (
        required_terms_hit / required_terms_total if required_terms_total else 1.0
    )

    similarity_ratio = SequenceMatcher(
        None, normalized_expected, normalized_predicted
    ).ratio()

    return OcrEvalMetrics(
        exact_match=expected == predicted,
        normalized_exact_match=normalized_expected == normalized_predicted,
        similarity_ratio=similarity_ratio,
        length_delta=len(predicted) - len(expected),
        required_terms_total=required_terms_total,
        required_terms_hit=required_terms_hit,
        required_terms_recall=required_terms_recall,
        error=error,
    )


def evaluate_ocr_batch(
    cases: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
) -> OcrEvalSummary:
    cases_by_id = {str(case.get("case_id")): case for case in cases}
    predicted_case_ids: set[str] = set()
    records: list[OcrEvalRecord] = []

    for prediction in predictions:
        case_id = str(prediction.get("case_id"))
        case = cases_by_id.get(case_id)
        if not case:
            continue

        predicted_case_ids.add(case_id)
        error = prediction.get("error")
        metrics = evaluate_ocr_prediction(
            expected_text=str(case.get("expected_text") or ""),
            predicted_text=str(prediction.get("predicted_text") or ""),
            required_terms=list(case.get("required_terms") or []),
            error=str(error) if error else None,
        )
        records.append(
            OcrEvalRecord(
                case_id=case_id,
                provider=str(prediction.get("provider") or "unknown"),
                metrics=metrics,
                latency_ms=_coerce_latency_ms(prediction.get("latency_ms")),
            )
        )

    missing_predictions_count = 0
    for case_id, case in cases_by_id.items():
        if case_id in predicted_case_ids:
            continue

        missing_predictions_count += 1
        records.append(
            OcrEvalRecord(
                case_id=case_id,
                provider="__missing__",
                metrics=evaluate_ocr_prediction(
                    expected_text=str(case.get("expected_text") or ""),
                    predicted_text="",
                    required_terms=list(case.get("required_terms") or []),
                    error="missing_prediction",
                ),
                latency_ms=None,
            )
        )

    by_provider = _summarize_by_provider(records)
    error_predictions_count = sum(
        1
        for record in records
        if record.provider != "__missing__" and record.metrics.error is not None
    )

    return OcrEvalSummary(
        total_cases=len(cases),
        total_predictions=len(predictions),
        evaluated_count=len(records),
        missing_predictions_count=missing_predictions_count,
        error_predictions_count=error_predictions_count,
        by_provider=by_provider,
        records=records,
    )


def _coerce_latency_ms(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _summarize_by_provider(
    records: list[OcrEvalRecord],
) -> dict[str, OcrProviderEvalSummary]:
    grouped: dict[str, list[OcrEvalRecord]] = defaultdict(list)
    for record in records:
        if record.provider == "__missing__":
            continue
        grouped[record.provider].append(record)

    summaries: dict[str, OcrProviderEvalSummary] = {}
    for provider, provider_records in grouped.items():
        latencies = [
            record.latency_ms
            for record in provider_records
            if record.latency_ms is not None
        ]
        total = len(provider_records)
        summaries[provider] = OcrProviderEvalSummary(
            provider=provider,
            total_predictions=total,
            exact_matches=sum(1 for record in provider_records if record.metrics.exact_match),
            normalized_exact_matches=sum(
                1 for record in provider_records if record.metrics.normalized_exact_match
            ),
            avg_similarity_ratio=_average(
                record.metrics.similarity_ratio for record in provider_records
            ),
            avg_required_terms_recall=_average(
                record.metrics.required_terms_recall for record in provider_records
            ),
            error_count=sum(1 for record in provider_records if record.metrics.error),
            avg_latency_ms=_average(latencies) if latencies else None,
        )

    return summaries


def _average(values: Any) -> float:
    items = list(values)
    if not items:
        return 0.0
    return sum(items) / len(items)
