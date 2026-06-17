from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.llm import nlp_service as default_llm_service
from app.services.ocr_service import ocr_service as default_ocr_service
from app.services.recognition_quality import detect_quality_warnings


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_PROVIDERS = ("baidu", "rapidocr")
MANUAL_CONCLUSION_SUGGESTIONS = (
    "usable",
    "partially_usable",
    "unusable",
    "need_crop",
    "need_manual_fix",
)


def collect_image_paths(input_path: str | Path) -> list[Path]:
    path = Path(input_path)
    if path.is_file():
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            raise ValueError(f"Unsupported image file extension: {path.suffix}")
        return [path]
    if not path.is_dir():
        raise FileNotFoundError(f"Input path does not exist: {path}")
    return sorted(
        [item for item in path.iterdir() if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS],
        key=lambda item: item.name.lower(),
    )


def parse_providers(value: str | None) -> list[str]:
    if not value:
        return list(DEFAULT_PROVIDERS)
    providers = [item.strip().lower() for item in value.split(",") if item.strip()]
    if not providers:
        raise ValueError("--providers must include at least one provider")
    return providers


def _warning_codes(warnings: list[Any]) -> list[str]:
    codes: list[str] = []
    for warning in warnings:
        code = getattr(warning, "code", None)
        if code is None and isinstance(warning, dict):
            code = warning.get("code")
        if code:
            codes.append(str(code))
    return codes


def _empty_result(image_path: Path, provider: str, *, llm_enabled: bool) -> dict[str, Any]:
    return {
        "image_path": str(image_path),
        "image_name": image_path.name,
        "provider": provider,
        "success": False,
        "error_message": "",
        "elapsed_ms": 0,
        "raw_text": "",
        "raw_text_length": 0,
        "quality_warnings": [],
        "llm_enabled": llm_enabled,
        "llm_success": False,
        "llm_error_message": "",
        "llm_corrected_text": "",
        "llm_tags": [],
        "knowledge_tags": [],
        "manual_conclusion": "",
        "notes": "",
    }


def evaluate_image_provider(
    image_path: Path,
    provider: str,
    *,
    with_llm: bool,
    ocr_service: Any,
    llm_service: Any,
) -> dict[str, Any]:
    result = _empty_result(image_path, provider, llm_enabled=with_llm)
    started_at = time.perf_counter()

    try:
        ocr_result = ocr_service.recognize(str(image_path), provider_name=provider)
    except Exception as exc:
        result["elapsed_ms"] = int((time.perf_counter() - started_at) * 1000)
        result["error_message"] = str(exc)
        return result

    measured_ms = int((time.perf_counter() - started_at) * 1000)
    result["success"] = bool(getattr(ocr_result, "success", False))
    result["error_message"] = str(getattr(ocr_result, "error", "") or "")
    result["elapsed_ms"] = int(getattr(ocr_result, "latency_ms", 0) or measured_ms)
    result["raw_text"] = str(getattr(ocr_result, "text", "") or "")
    result["raw_text_length"] = len(result["raw_text"])

    if result["success"]:
        text_for_warnings = result["raw_text"]
        llm_cleaned_text = ""

        if with_llm:
            try:
                llm_result = llm_service.analyze(result["raw_text"])
                result["llm_success"] = bool(llm_result.get("success"))
                if result["llm_success"]:
                    llm_cleaned_text = str(llm_result.get("corrected_text") or "")
                    tags = llm_result.get("knowledge_tags", llm_result.get("tags", [])) or []
                    result["llm_corrected_text"] = llm_cleaned_text
                    result["llm_tags"] = tags
                    result["knowledge_tags"] = tags
                    text_for_warnings = llm_cleaned_text or result["raw_text"]
                else:
                    result["llm_error_message"] = str(
                        llm_result.get("detail") or llm_result.get("error") or "llm_failed"
                    )
                    llm_cleaned_text = str(llm_result.get("corrected_text") or "")
            except Exception as exc:
                result["llm_error_message"] = str(exc)

        result["quality_warnings"] = _warning_codes(
            detect_quality_warnings(
                text_for_warnings,
                raw_ocr_text=result["raw_text"],
                llm_cleaned_text=llm_cleaned_text,
            )
        )

    return result


def run_comparison(
    *,
    input_path: str | Path,
    providers: list[str],
    with_llm: bool,
    ocr_service: Any = default_ocr_service,
    llm_service: Any = default_llm_service,
) -> list[dict[str, Any]]:
    images = collect_image_paths(input_path)
    results: list[dict[str, Any]] = []
    for image_path in images:
        for provider in providers:
            results.append(
                evaluate_image_provider(
                    image_path,
                    provider,
                    with_llm=with_llm,
                    ocr_service=ocr_service,
                    llm_service=llm_service,
                )
            )
    return results


def _escape_table(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _format_bool(value: bool) -> str:
    return "yes" if value else "no"


def _code_block_text(value: str) -> str:
    return (value or "").replace("```", "`\u200b``")


def render_markdown_report(
    results: list[dict[str, Any]],
    *,
    generated_at: str,
    input_value: str,
    providers: list[str],
    with_llm: bool,
) -> str:
    lines = [
        "# OCR Provider A/B Smoke Report",
        "",
        "## Run Info",
        "",
        f"- generated_at: {generated_at}",
        f"- input: {input_value}",
        f"- providers: {', '.join(providers)}",
        f"- with_llm: {_format_bool(with_llm)}",
        f"- total_images: {len({item['image_path'] for item in results})}",
        "",
        "manual_conclusion 建议值："
        + ", ".join(MANUAL_CONCLUSION_SUGGESTIONS)
        + "。默认留空，由人工复核后填写。",
        "",
        "## Summary",
        "",
        "| Image | Provider | Success | OCR ms | Text Length | Warnings | LLM | Manual Conclusion |",
        "| --- | --- | --- | ---: | ---: | --- | --- | --- |",
    ]

    for item in results:
        warnings = ", ".join(item["quality_warnings"]) if item["quality_warnings"] else "-"
        llm_status = "-" if not item["llm_enabled"] else _format_bool(bool(item["llm_success"]))
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_table(item["image_name"]),
                    _escape_table(item["provider"]),
                    _format_bool(bool(item["success"])),
                    str(item["elapsed_ms"]),
                    str(item["raw_text_length"]),
                    _escape_table(warnings),
                    llm_status,
                    _escape_table(item["manual_conclusion"]),
                ]
            )
            + " |"
        )

    by_image: dict[str, list[dict[str, Any]]] = {}
    for item in results:
        by_image.setdefault(item["image_name"], []).append(item)

    for image_name, image_results in by_image.items():
        lines.extend(["", f"## {image_name}", ""])
        for item in image_results:
            warnings = ", ".join(item["quality_warnings"]) if item["quality_warnings"] else "-"
            lines.extend(
                [
                    f"### {item['provider']}",
                    "",
                    f"- success: {_format_bool(bool(item['success']))}",
                    f"- elapsed_ms: {item['elapsed_ms']}",
                    f"- quality_warnings: {warnings}",
                    f"- error_message: {item['error_message'] or '-'}",
                    f"- llm_enabled: {_format_bool(bool(item['llm_enabled']))}",
                    f"- llm_success: {_format_bool(bool(item['llm_success']))}",
                    f"- llm_error_message: {item['llm_error_message'] or '-'}",
                    "",
                    "OCR raw text:",
                    "",
                    "```text",
                    _code_block_text(item["raw_text"]),
                    "```",
                    "",
                ]
            )
            if item["llm_enabled"]:
                lines.extend(
                    [
                        "LLM corrected text:",
                        "",
                        "```text",
                        _code_block_text(item["llm_corrected_text"]),
                        "```",
                        "",
                        f"- knowledge_tags: {', '.join(map(str, item['knowledge_tags'])) if item['knowledge_tags'] else '-'}",
                        "",
                    ]
                )

    return "\n".join(lines).rstrip() + "\n"


def write_outputs(
    results: list[dict[str, Any]],
    *,
    output_path: str | Path,
    json_output_path: str | Path | None,
    input_value: str,
    providers: list[str],
    with_llm: bool,
) -> None:
    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        render_markdown_report(
            results,
            generated_at=generated_at,
            input_value=input_value,
            providers=providers,
            with_llm=with_llm,
        ),
        encoding="utf-8",
    )
    if json_output_path:
        json_output = Path(json_output_path)
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(
            json.dumps(
                {
                    "metadata": {
                        "generated_at": generated_at,
                        "input": input_value,
                        "providers": providers,
                        "with_llm": with_llm,
                        "total_images": len({item["image_path"] for item in results}),
                    },
                    "results": results,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare OCR providers on the same image set.")
    parser.add_argument("--input", required=True, help="Image file or directory containing images.")
    parser.add_argument("--providers", default=",".join(DEFAULT_PROVIDERS), help="Comma-separated provider list.")
    parser.add_argument("--output", required=True, help="Markdown report output path.")
    parser.add_argument("--json-output", help="Optional JSON output path.")
    parser.add_argument("--with-llm", action="store_true", help="Also run LLM cleanup after successful OCR.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    providers = parse_providers(args.providers)
    results = run_comparison(
        input_path=args.input,
        providers=providers,
        with_llm=args.with_llm,
    )
    write_outputs(
        results,
        output_path=args.output,
        json_output_path=args.json_output,
        input_value=args.input,
        providers=providers,
        with_llm=args.with_llm,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
