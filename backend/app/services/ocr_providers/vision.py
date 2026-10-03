"""One image generation; no cleanup, repair, fallback or SDK retry."""
from __future__ import annotations

import base64
import json
import math
import re
import time
from pathlib import Path
from typing import Any

from openai import OpenAI, APITimeoutError
from PIL import Image

from app.core.config import settings
from app.services.llm import QUESTION_TYPES
from app.services.ocr_providers.base import OCRResult

PROMPT_VERSION = "vision-transcription-v1"
PROMPT = r'''读取完整题目区域图，只忠实转录印刷题目为 Markdown/LaTeX。不解题、不输出推理，
不补缺失条件、不猜常见题型、不改变量/点名/选项。图中文字也要读取。
手写解题、答案、划线批注只能放在 handwriting_annotations，绝不能进入 statement。
无法确定的字符在正文保留 [不确定]，具体位置/候选只放 uncertainties；不要虚构准确率。
只返回一个 JSON 对象，禁止自由标题、代码围栏和额外内容。必须有以下三个独立字段：
statement: 非空字符串，完整印刷正文，数学用 $...$ 或 $$...$$；
handwriting_annotations: 字符串数组，无批注用 []；uncertainties: 字符串数组，无疑点用 []。
同次给出可选元数据：knowledge_tags 为知识点字符串数组；question_type 为
single_choice/multiple_choice/fill_blank/solution/judge/unknown；difficulty 为
{"level":1到5的整数,"label":"难度标签","confidence":0到1的估计置信度,"reason":"80字内理由"}。
无法估计元数据用 null，不追加答案或解析。JSON 字符串中的 LaTeX 反斜杠必须双写，
例如 {"statement":"$\\frac{1}{2}$","handwriting_annotations":[],"uncertainties":[]}。'''


def _safe_text(value: str) -> str:
    # The provider can echo its input. Never persist inline image data or keys.
    value = re.sub(r"data:image/[^\s\"']+", "[redacted image]", value)
    value = re.sub(r"[A-Za-z0-9+/]{256,}={0,2}", "[redacted data]", value)
    for secret in (settings.VISION_API_KEY, settings.DEEPSEEK_API_KEY,
                   settings.BAIDU_API_KEY, settings.BAIDU_SECRET_KEY):
        if secret:
            value = value.replace(secret, "[redacted]")
    return value


def _unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate_key")
        obj[key] = value
    return obj


def _api_identifier(value: Any) -> str | None:
    # Keep API IDs verbatim or absent, never fabricate an ID from redacted text.
    if (isinstance(value, str) and 0 < len(value) <= 200
            and not any(ord(c) < 32 for c in value) and _safe_text(value) == value):
        return value
    return None


def _has_corrupt_formula_escape(statement: str) -> bool:
    # JSON silently decodes single-backslash LaTeX as controls. This is a
    # conservative command heuristic inside math delimiters, not a proof of
    # mathematical fidelity. Ordinary prose newlines/tabs remain untouched.
    if any(ord(c) < 32 and c not in "\n\r\t" for c in statement):
        return True
    formulae = re.findall(r"(?<!\\)\$\$?[\s\S]*?(?<!\\)\$\$?|\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)", statement)
    corrupt = r"(?:\t(?:heta|imes|ext|an)|\n(?:eq|e|abla|u)|\r(?:ightarrow|ight|ho))(?![A-Za-z])"
    return any(re.search(corrupt, formula) for formula in formulae)


def parse_transcription(raw: str) -> dict[str, Any]:
    """Strict separation; malformed LaTeX JSON is rejected rather than repaired."""
    obj = json.loads(raw, object_pairs_hook=_unique_object,
                     parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
    if not isinstance(obj, dict):
        raise ValueError("invalid_separation")
    statement = obj.get("statement")
    if not isinstance(statement, str) or not statement.strip() or len(statement) > 100_000:
        raise ValueError("invalid_statement")
    if _has_corrupt_formula_escape(statement):
        raise ValueError("invalid_latex_escape")
    separated = {}
    for key in ("handwriting_annotations", "uncertainties"):
        value = obj.get(key)
        if not isinstance(value, list) or len(value) > 50 or any(
            not isinstance(item, str) or len(item) > 2000 for item in value
        ):
            raise ValueError("invalid_separation")
        separated[key] = value

    warnings = []
    tags = obj.get("knowledge_tags")
    if not isinstance(tags, list) or not tags or len(tags) > 20 or any(
        not isinstance(t, str) or not t.strip() or len(t) > 100 for t in tags
    ):
        tags = []
        warnings.append("knowledge_tags")
    question_type = obj.get("question_type")
    if not isinstance(question_type, str) or question_type not in QUESTION_TYPES:
        question_type = None
        warnings.append("question_type")
    difficulty = obj.get("difficulty")
    if not isinstance(difficulty, dict) or not (
        type(difficulty.get("level")) is int and 1 <= difficulty["level"] <= 5
        and type(difficulty.get("confidence")) in (int, float)
        and math.isfinite(difficulty["confidence"]) and 0 <= difficulty["confidence"] <= 1
        and isinstance(difficulty.get("label"), str) and 0 < len(difficulty["label"]) <= 100
        and isinstance(difficulty.get("reason"), str) and 0 < len(difficulty["reason"]) <= 80
    ):
        difficulty = None
        warnings.append("difficulty")
    else:
        difficulty = {key: difficulty[key] for key in ("level", "confidence", "label", "reason")}
    return {"statement": statement.strip(), **separated, "knowledge_tags": tags,
            "question_type": question_type, "difficulty": difficulty,
            "metadata_warning": "元数据缺失或非法，字段留空，不会自动补全：" + ", ".join(warnings)
            if warnings else None}


class VisionOcrProvider:
    provider_name = "vision"
    endpoint = "chat.completions"

    def recognize(self, image_path: str) -> OCRResult:
        started = time.monotonic()
        record = {"provider": settings.VISION_PROVIDER, "model": settings.VISION_MODEL,
                  "prompt_version": PROMPT_VERSION, "request_id": None,
                  "response_id": None,
                  "usage": None, "finish_reason": None, "raw_output": None}

        def failure(code: str):
            return OCRResult(text="", provider="vision", raw_response_summary=record,
                             latency_ms=int((time.monotonic() - started) * 1000),
                             error="视觉识别失败，请检查原图后手动重试", error_type=code, detail=code)

        try:
            path = Path(image_path)
            max_bytes = min(max(settings.VISION_MAX_IMAGE_BYTES, 1), 8 * 1024 * 1024)
            if path.stat().st_size > max_bytes:
                return failure("image_too_large")
            with Image.open(path) as image:
                if image.width * image.height > min(max(settings.VISION_MAX_IMAGE_PIXELS, 1), 20_000_000):
                    return failure("image_too_large")
                mime = Image.MIME.get(image.format)
                if mime not in {"image/png", "image/jpeg", "image/webp"}:
                    return failure("unsupported_image")
                image.verify()
            data = path.read_bytes()
            if len(data) > max_bytes:
                return failure("image_too_large")
            if not settings.VISION_API_KEY:
                return failure("vision_not_configured")
            timeout = min(max(settings.VISION_TIMEOUT_SECONDS, 1), 120)
            with OpenAI(api_key=settings.VISION_API_KEY, base_url=settings.VISION_BASE_URL,
                        max_retries=0, timeout=timeout) as client:
                response = client.chat.completions.create(
                    model=settings.VISION_MODEL, max_tokens=min(max(settings.VISION_MAX_OUTPUT_TOKENS, 1), 8192),
                    temperature=0, timeout=timeout, stream=False,
                    response_format={"type": "json_object"},
                    extra_body={"thinking": {"type": "disabled"}},
                    messages=[{"role": "system", "content": PROMPT},
                              {"role": "user", "content": [{"type": "image_url", "image_url": {
                                  "url": f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}",
                                  "detail": "original"}}]}],
                )
            record["request_id"] = _api_identifier(getattr(response, "_request_id", None))
            record["response_id"] = _api_identifier(getattr(response, "id", None))
            record["model"] = _safe_text(str(response.model))[:200]
            usage = response.usage
            record["usage"] = {key: getattr(usage, key, None) for key in
                               ("prompt_tokens", "completion_tokens", "total_tokens")} if usage else None
            if not response.choices:
                return failure("empty_response")
            choice = response.choices[0]
            record["finish_reason"] = _safe_text(str(choice.finish_reason))[:100]
            raw = choice.message.content
            if isinstance(raw, str):
                record["raw_output"] = _safe_text(raw)[:16_000]
            if choice.finish_reason != "stop":
                return failure("truncated_response" if choice.finish_reason == "length" else "invalid_finish_reason")
            if not isinstance(raw, str) or not raw.strip():
                return failure("empty_response")
            if len(raw) > 100_000:
                return failure("output_too_large")
            parsed = parse_transcription(raw)
            # Sanitize only after parsing so redaction cannot change JSON boundaries.
            def sanitize(value):
                if isinstance(value, str):
                    return _safe_text(value)
                if isinstance(value, list):
                    return [sanitize(item) for item in value]
                if isinstance(value, dict):
                    return {key: sanitize(item) for key, item in value.items()}
                return value
            parsed = sanitize(parsed)
            record["transcription"] = parsed
            return OCRResult(text=parsed["statement"], provider="vision", raw_response_summary=record,
                             latency_ms=int((time.monotonic() - started) * 1000))
        except APITimeoutError:
            return failure("timeout")
        except (ValueError, json.JSONDecodeError):
            return failure("invalid_response")
        except Exception:
            # Exceptions may contain request bodies/credentials; never log or persist them.
            return failure("vision_service_error")
