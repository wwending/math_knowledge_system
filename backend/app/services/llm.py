import json
import os
import re
import time
from typing import Any

from loguru import logger
from openai import APIConnectionError, APIError, APITimeoutError, AuthenticationError, OpenAI

from app.core.config import settings


QUESTION_TYPES = {"single_choice", "multiple_choice", "fill_blank", "solution", "judge", "unknown"}
PREVIEW_LIMIT = 200
RAW_RESPONSE_PREVIEW_LIMIT = 1000
DEFAULT_LLM_MAX_TOKENS = 2048
DEFAULT_LLM_TIMEOUT_SECONDS = 45
DEFAULT_LLM_THINKING_MODE = "disabled"


def normalize_latex_delimiters(text: str) -> str:
    if not text:
        return text

    text = re.sub(r"\\\[(.*?)\\\]", r"$$\1$$", text, flags=re.DOTALL)
    return re.sub(r"\\\((.*?)\\\)", r"$\1$", text, flags=re.DOTALL)


def _truncate_text(value: Any, limit: int = PREVIEW_LIMIT) -> str | None:
    if value is None:
        return None
    text = str(value)
    if len(text) <= limit:
        return text
    return text[:limit]


def _safe_get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _safe_payload(value: Any, *, max_depth: int = 4) -> Any:
    if max_depth <= 0:
        return _truncate_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _truncate_text(value)
    if isinstance(value, (list, tuple)):
        return [_safe_payload(item, max_depth=max_depth - 1) for item in list(value)[:5]]
    if isinstance(value, dict):
        return {str(key): _safe_payload(item, max_depth=max_depth - 1) for key, item in list(value.items())[:20]}
    if hasattr(value, "model_dump"):
        try:
            return _safe_payload(value.model_dump(), max_depth=max_depth - 1)
        except Exception:
            pass
    if hasattr(value, "__dict__"):
        return _safe_payload(vars(value), max_depth=max_depth - 1)
    return _truncate_text(repr(value))


def _safe_raw_response_preview(response: Any) -> str:
    try:
        payload = _safe_payload(response)
        preview = json.dumps(payload, ensure_ascii=False, default=str)
    except Exception:
        preview = repr(response)
    return preview[:RAW_RESPONSE_PREVIEW_LIMIT]


def _summarize_deepseek_response(
    response: Any,
    *,
    input_text_len: int,
    configured_model: str,
    timeout_seconds: float | int | None,
) -> dict[str, Any]:
    choices = _safe_get(response, "choices")
    choices_count = len(choices) if isinstance(choices, list) else 0
    first_choice = choices[0] if choices_count else None
    message = _safe_get(first_choice, "message") if first_choice is not None else None
    content = _safe_get(message, "content") if message is not None else None
    refusal = _safe_get(message, "refusal") if message is not None else None
    reasoning_content = _safe_get(message, "reasoning_content") if message is not None else None
    tool_calls = _safe_get(message, "tool_calls") if message is not None else None
    usage = _safe_get(response, "usage")

    content_text = "" if content is None else str(content)
    reasoning_text = "" if reasoning_content is None else str(reasoning_content)

    return {
        "response_type": type(response).__name__,
        "response_id": _safe_get(response, "id"),
        "response_model": _safe_get(response, "model"),
        "created": _safe_get(response, "created"),
        "choices_count": choices_count,
        "finish_reason": _safe_get(first_choice, "finish_reason") if first_choice is not None else None,
        "message_role": _safe_get(message, "role") if message is not None else None,
        "content_type": type(content).__name__ if content is not None else None,
        "content_len": len(content_text),
        "content_preview": _truncate_text(content_text),
        "has_refusal": bool(refusal),
        "refusal_preview": _truncate_text(refusal),
        "has_reasoning_content": bool(reasoning_content),
        "reasoning_content_len": len(reasoning_text),
        "reasoning_content_preview": _truncate_text(reasoning_text),
        "has_tool_calls": bool(tool_calls),
        "usage_prompt_tokens": _safe_get(usage, "prompt_tokens"),
        "usage_completion_tokens": _safe_get(usage, "completion_tokens"),
        "usage_total_tokens": _safe_get(usage, "total_tokens"),
        "raw_response_preview": _safe_raw_response_preview(response),
        "input_text_len": input_text_len,
        "configured_model": configured_model,
        "timeout_seconds": timeout_seconds,
    }


def _format_deepseek_detail(prefix: str, summary: dict[str, Any]) -> str:
    finish_reason = summary.get("finish_reason") or "unknown"
    completion_tokens = summary.get("usage_completion_tokens")
    if completion_tokens is None:
        completion_tokens = "unknown"
    return (
        f"{prefix}: choices_count={summary.get('choices_count', 0)} "
        f"finish_reason={finish_reason} content_len={summary.get('content_len', 0)} "
        f"completion_tokens={completion_tokens}"
    )


def _get_env_value(name: str) -> str | None:
    raw_value = os.getenv(name)
    if raw_value is not None:
        return raw_value
    env_file = settings.BASE_DIR / ".env"
    if not env_file.exists():
        return None
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            if key.strip() == name:
                return value.strip().strip('"').strip("'")
    except OSError as exc:
        logger.warning("Failed to read env file for {}: {}", name, exc)
    return None


def _get_int_env(name: str, default: int) -> int:
    raw_value = _get_env_value(name)
    if raw_value is None or not raw_value.strip():
        return default
    try:
        value = int(raw_value)
    except ValueError:
        logger.warning("Invalid integer env {}={}, fallback={}", name, raw_value, default)
        return default
    return value if value > 0 else default


def _get_llm_max_tokens() -> int:
    return _get_int_env("LLM_MAX_TOKENS", DEFAULT_LLM_MAX_TOKENS)


def _get_llm_timeout_seconds(*, include_metadata: bool) -> int:
    if include_metadata:
        return _get_int_env(
            "LLM_METADATA_TIMEOUT_SECONDS",
            settings.DEEPSEEK_METADATA_TIMEOUT_SECONDS,
        )
    return _get_int_env("LLM_TIMEOUT_SECONDS", DEFAULT_LLM_TIMEOUT_SECONDS)


def _get_llm_thinking_mode() -> str:
    return (_get_env_value("LLM_THINKING_MODE") or DEFAULT_LLM_THINKING_MODE).strip().lower() or DEFAULT_LLM_THINKING_MODE


def _build_failure(
    error_type: str,
    error: str,
    *,
    detail: str | None = None,
    corrected_text: str = "",
    tags: list[str] | None = None,
    cost_seconds: float = 0.0,
    perf: dict[str, int] | None = None,
) -> dict[str, Any]:
    return {
        "success": False,
        "corrected_text": corrected_text,
        "tags": tags or [],
        "knowledge_tags": tags or [],
        "question_type": "unknown",
        "difficulty": None,
        "metadata_warning": None,
        "cost_seconds": round(cost_seconds, 2),
        "error_type": error_type,
        "error": error,
        "detail": detail or error,
        "_perf": perf or {"prompt_ms": 0, "api_ms": 0, "parse_ms": 0},
    }


def _normalize_question_type(raw_question_type: Any) -> str:
    if not isinstance(raw_question_type, str):
        return "unknown"
    question_type = raw_question_type.strip()
    return question_type if question_type in QUESTION_TYPES else "unknown"


def _normalize_difficulty(raw_difficulty: Any) -> tuple[dict[str, Any] | None, str | None]:
    if raw_difficulty is None:
        return None, None
    if not isinstance(raw_difficulty, dict):
        logger.warning("DeepSeek difficulty has invalid type: {}", raw_difficulty)
        return None, "difficulty_fallback"

    level = raw_difficulty.get("level")
    confidence = raw_difficulty.get("confidence")
    label = raw_difficulty.get("label")
    reason = raw_difficulty.get("reason")

    if not isinstance(level, int) or level < 1 or level > 5:
        logger.warning("DeepSeek difficulty level is invalid: {}", raw_difficulty)
        return None, "difficulty_fallback"

    if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
        logger.warning("DeepSeek difficulty confidence is invalid: {}", raw_difficulty)
        return None, "difficulty_fallback"

    normalized_label = label.strip() if isinstance(label, str) and label.strip() else None
    normalized_reason = reason.strip() if isinstance(reason, str) and reason.strip() else None
    if normalized_reason and len(normalized_reason) > 80:
        normalized_reason = normalized_reason[:80]

    return (
        {
            "level": level,
            "label": normalized_label,
            "confidence": float(confidence),
            "reason": normalized_reason,
        },
        None,
    )


class NLPService:
    def __init__(self):
        self.api_key = settings.DEEPSEEK_API_KEY
        self.base_url = settings.DEEPSEEK_BASE_URL
        self.client = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        if not self.api_key or not self.base_url:
            logger.warning("DeepSeek credentials are not configured")
            self.client = None
            return

        try:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
            logger.success("DeepSeek client initialized")
        except Exception:
            self.client = None
            logger.exception("Failed to initialize DeepSeek client")

    def analyze(self, text: str, *, include_metadata: bool = False) -> dict[str, Any]:
        if not text:
            return {
                "success": True,
                "corrected_text": "",
                "tags": [],
                "knowledge_tags": [],
                "question_type": "unknown",
                "difficulty": None,
                "metadata_warning": None,
                "cost_seconds": 0.0,
                "_perf": {"prompt_ms": 0, "api_ms": 0, "parse_ms": 0},
            }

        if not self.client:
            return _build_failure(
                "service_unavailable",
                "\u667a\u80fd\u6574\u7406\u670d\u52a1\u6682\u65f6\u4e0d\u53ef\u7528",
                detail="deepseek_client_unavailable",
                corrected_text=text,
            )

        started_at = time.time()
        prompt_started_at = time.time()
        metadata_instructions = ""
        metadata_response_shape = ""
        if include_metadata:
            metadata_instructions = """
10. 识别题型 question_type，只能从以下枚举选择：
    - single_choice：单选题
    - multiple_choice：多选题
    - fill_blank：填空题
    - solution：解答题
    - judge：判断题
    - unknown：未知
11. 评估五星难度 difficulty：
    - 1星：基础识记题，直接套概念或公式即可完成
    - 2星：基础应用题，单一知识点，一到两步计算
    - 3星：中等综合题，涉及两类知识点或多步推理
    - 4星：较难综合题，需要分类讨论、复杂计算或较强转化能力
    - 5星：压轴难题，需要抽象建模、创新构造或高综合能力
12. difficulty.level 必须是 1 到 5 的整数。
13. difficulty.confidence 必须是 0 到 1 的小数。
14. difficulty.reason 不超过 80 字。"""
            metadata_response_shape = """,
  "question_type": "single_choice",
  "difficulty": {
    "level": 3,
    "label": "中等",
    "confidence": 0.78,
    "reason": "涉及两类知识点或多步推理。"
  }"""

        prompt = f"""
你是一个高中数学 OCR 文本清洗与结构化工具。请对以下 OCR 识别出的数学题目文本进行清洗，并只返回 JSON。

任务要求：
1. 修正明显 OCR 错误，例如：
   - 将 '1n' 修正为 'ln'
   - 将错误识别的指数、根号、分式、三角函数符号修正为正确数学表达
   - 修正常见的数学符号识别错误
2. 将数学公式转换为标准 LaTeX 格式。
3. 行内公式必须使用 $...$ 包裹。
4. 块级公式、复杂方程组、联立公式、分段函数必须使用 $$...$$ 包裹。
5. 不要使用 \\(...\\) 作为行内公式分隔符。
6. 不要使用 \\[...\\] 作为块级公式分隔符。
7. 保持题目原意不变，不要自行补充题目没有给出的条件、答案或解析。
8. 中文题目保持中文表达。
9. 提取 3-5 个高中数学知识点标签。
10. 不解题，不证明，不分析，不输出推理过程。
11. 只修正 OCR，只规范 LaTeX，只返回 JSON。
{metadata_instructions}

原始 OCR 文本：
{text}

请务必只返回纯 JSON，不要包含 ```json 或 ``` 代码块标记。
JSON 输出样例如下：
{{
  "corrected_text": "修复后的完整题目文本，包含使用 $...$ 或 $$...$$ 包裹的 LaTeX 公式",
  "knowledge_tags": ["标签1", "标签2", "标签3"]{metadata_response_shape}
}}
"""
        prompt_ms = int((time.time() - prompt_started_at) * 1000)
        api_ms = 0
        timeout_seconds = _get_llm_timeout_seconds(include_metadata=include_metadata)
        max_tokens = _get_llm_max_tokens()
        thinking_mode = _get_llm_thinking_mode()

        try:
            api_started_at = time.time()
            response = self.client.chat.completions.create(
                model=settings.DEEPSEEK_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是一个高中数学 OCR 文本清洗与结构化工具。"
                            "你只修正 OCR，只规范 LaTeX，只返回 JSON。"
                            "不解题，不证明，不分析，不输出推理过程。"
                            "所有行内公式必须使用 $...$，所有块级公式必须使用 $$...$$，"
                            "不要使用 \\(...\\) 或 \\[...\\]。"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                stream=False,
                temperature=0.1,
                max_tokens=max_tokens,
                timeout=timeout_seconds,
                response_format={"type": "json_object"},
                extra_body={"thinking": {"type": thinking_mode}},
            )
            api_ms = int((time.time() - api_started_at) * 1000)
        except APITimeoutError:
            api_ms = int((time.time() - api_started_at) * 1000)
            logger.warning("DeepSeek call timed out")
            return _build_failure(
                "timeout",
                "\u667a\u80fd\u6574\u7406\u8d85\u65f6\uff0c\u5df2\u4fdd\u7559\u539f\u59cb\u8bc6\u522b\u7ed3\u679c",
                detail="deepseek_timeout",
                corrected_text=text,
                cost_seconds=time.time() - started_at,
                perf={"prompt_ms": prompt_ms, "api_ms": api_ms, "parse_ms": 0},
            )
        except AuthenticationError as exc:
            api_ms = int((time.time() - api_started_at) * 1000)
            logger.warning("DeepSeek authentication failed: {}", exc)
            return _build_failure(
                "auth_failed",
                "\u667a\u80fd\u6574\u7406\u670d\u52a1\u8ba4\u8bc1\u5931\u8d25",
                detail=f"deepseek_auth_failed:{exc}",
                corrected_text=text,
                cost_seconds=time.time() - started_at,
                perf={"prompt_ms": prompt_ms, "api_ms": api_ms, "parse_ms": 0},
            )
        except APIConnectionError as exc:
            api_ms = int((time.time() - api_started_at) * 1000)
            logger.warning("DeepSeek connection failed: {}", exc)
            return _build_failure(
                "service_unavailable",
                "\u667a\u80fd\u6574\u7406\u670d\u52a1\u6682\u65f6\u4e0d\u53ef\u7528",
                detail=f"deepseek_connection_failed:{exc}",
                corrected_text=text,
                cost_seconds=time.time() - started_at,
                perf={"prompt_ms": prompt_ms, "api_ms": api_ms, "parse_ms": 0},
            )
        except APIError as exc:
            api_ms = int((time.time() - api_started_at) * 1000)
            logger.warning("DeepSeek API error: {}", exc)
            return _build_failure(
                "service_error",
                "\u667a\u80fd\u6574\u7406\u670d\u52a1\u8c03\u7528\u5931\u8d25",
                detail=f"deepseek_api_error:{exc}",
                corrected_text=text,
                cost_seconds=time.time() - started_at,
                perf={"prompt_ms": prompt_ms, "api_ms": api_ms, "parse_ms": 0},
            )
        except Exception:
            api_ms = int((time.time() - api_started_at) * 1000)
            logger.exception("Unexpected DeepSeek failure")
            return _build_failure(
                "service_error",
                "\u667a\u80fd\u6574\u7406\u670d\u52a1\u8c03\u7528\u5931\u8d25",
                detail="deepseek_unexpected_error",
                corrected_text=text,
                cost_seconds=time.time() - started_at,
                perf={"prompt_ms": prompt_ms, "api_ms": api_ms, "parse_ms": 0},
            )

        parse_started_at = time.time()
        response_summary = _summarize_deepseek_response(
            response,
            input_text_len=len(text),
            configured_model=settings.DEEPSEEK_MODEL,
            timeout_seconds=timeout_seconds,
        )
        choices = _safe_get(response, "choices")
        if not isinstance(choices, list) or not choices:
            logger.warning("DeepSeek returned unexpected response shape: {}", response_summary)
            return _build_failure(
                "invalid_response",
                "\u667a\u80fd\u6574\u7406\u670d\u52a1\u8fd4\u56de\u4e86\u5f02\u5e38\u6570\u636e",
                detail=_format_deepseek_detail("deepseek_invalid_choice_shape", response_summary),
                corrected_text=text,
                cost_seconds=time.time() - started_at,
                perf={
                    "prompt_ms": prompt_ms,
                    "api_ms": api_ms,
                    "parse_ms": int((time.time() - parse_started_at) * 1000),
                },
            )
        first_choice = choices[0]
        message = _safe_get(first_choice, "message")
        if message is None:
            logger.warning("DeepSeek returned choice without message: {}", response_summary)
            return _build_failure(
                "invalid_response",
                "\u667a\u80fd\u6574\u7406\u670d\u52a1\u8fd4\u56de\u4e86\u5f02\u5e38\u6570\u636e",
                detail=_format_deepseek_detail("deepseek_invalid_message_shape", response_summary),
                corrected_text=text,
                cost_seconds=time.time() - started_at,
                perf={
                    "prompt_ms": prompt_ms,
                    "api_ms": api_ms,
                    "parse_ms": int((time.time() - parse_started_at) * 1000),
                },
            )

        result_content = _safe_get(message, "content") or ""

        clean_json = result_content.replace("```json", "").replace("```", "").strip()
        if not clean_json:
            logger.warning("DeepSeek returned empty content: {}", response_summary)
            empty_content_detail = "deepseek_empty_content"
            if response_summary.get("finish_reason") == "length":
                empty_content_detail = "deepseek_length_exhausted_empty_content"
            return _build_failure(
                "invalid_response",
                "\u667a\u80fd\u6574\u7406\u670d\u52a1\u8fd4\u56de\u4e86\u7a7a\u6570\u636e",
                detail=_format_deepseek_detail(empty_content_detail, response_summary),
                corrected_text=text,
                cost_seconds=time.time() - started_at,
                perf={
                    "prompt_ms": prompt_ms,
                    "api_ms": api_ms,
                    "parse_ms": int((time.time() - parse_started_at) * 1000),
                },
            )

        try:
            result = json.loads(clean_json)
        except json.JSONDecodeError:
            logger.warning(
                "DeepSeek returned non-JSON content preview={} response_summary={}",
                _truncate_text(clean_json),
                response_summary,
            )
            return _build_failure(
                "invalid_response",
                "\u667a\u80fd\u6574\u7406\u670d\u52a1\u8fd4\u56de\u4e86\u65e0\u6548\u683c\u5f0f",
                detail=f"deepseek_non_json:{_truncate_text(clean_json)}",
                corrected_text=text,
                cost_seconds=time.time() - started_at,
                perf={
                    "prompt_ms": prompt_ms,
                    "api_ms": api_ms,
                    "parse_ms": int((time.time() - parse_started_at) * 1000),
                },
            )

        if "corrected_text" not in result:
            logger.warning("DeepSeek response missing corrected_text: {}", response_summary)
            return _build_failure(
                "invalid_response",
                "\u667a\u80fd\u6574\u7406\u670d\u52a1\u8fd4\u56de\u4e86\u5f02\u5e38\u7ed3\u6784",
                detail=_format_deepseek_detail("deepseek_missing_corrected_text", response_summary),
                corrected_text=text,
                cost_seconds=time.time() - started_at,
                perf={
                    "prompt_ms": prompt_ms,
                    "api_ms": api_ms,
                    "parse_ms": int((time.time() - parse_started_at) * 1000),
                },
            )

        corrected_text = result.get("corrected_text")
        raw_tags = result.get("knowledge_tags", result.get("tags", []))

        if not isinstance(corrected_text, str):
            logger.warning("DeepSeek corrected_text has invalid type: {}", response_summary)
            return _build_failure(
                "invalid_response",
                "\u667a\u80fd\u6574\u7406\u670d\u52a1\u8fd4\u56de\u4e86\u5f02\u5e38\u7ed3\u6784",
                detail=_format_deepseek_detail("deepseek_invalid_corrected_text", response_summary),
                corrected_text=text,
                cost_seconds=time.time() - started_at,
                perf={
                    "prompt_ms": prompt_ms,
                    "api_ms": api_ms,
                    "parse_ms": int((time.time() - parse_started_at) * 1000),
                },
            )

        corrected_text = normalize_latex_delimiters(corrected_text)

        if not isinstance(raw_tags, list):
            logger.warning("DeepSeek tags has invalid type: {}", response_summary)
            return _build_failure(
                "invalid_response",
                "\u667a\u80fd\u6574\u7406\u670d\u52a1\u8fd4\u56de\u4e86\u5f02\u5e38\u7ed3\u6784",
                detail=_format_deepseek_detail("deepseek_invalid_tags", response_summary),
                corrected_text=text,
                cost_seconds=time.time() - started_at,
                perf={
                    "prompt_ms": prompt_ms,
                    "api_ms": api_ms,
                    "parse_ms": int((time.time() - parse_started_at) * 1000),
                },
            )

        normalized_tags: list[str] = []
        for tag in raw_tags:
            if isinstance(tag, str) and tag.strip():
                normalized_tags.append(tag.strip())
                continue
            if isinstance(tag, dict) and isinstance(tag.get("label"), str) and tag["label"].strip():
                normalized_tags.append(tag["label"].strip())
                continue
            logger.warning("DeepSeek tag item has invalid shape: item_preview={} response_summary={}", _truncate_text(tag), response_summary)
            return _build_failure(
                "invalid_response",
                "\u667a\u80fd\u6574\u7406\u670d\u52a1\u8fd4\u56de\u4e86\u5f02\u5e38\u7ed3\u6784",
                detail=f"deepseek_invalid_tag_item:{_truncate_text(tag)}",
                corrected_text=text,
                cost_seconds=time.time() - started_at,
                perf={
                    "prompt_ms": prompt_ms,
                    "api_ms": api_ms,
                    "parse_ms": int((time.time() - parse_started_at) * 1000),
                },
            )

        difficulty = None
        metadata_warning = None
        if include_metadata:
            difficulty, metadata_warning = _normalize_difficulty(result.get("difficulty"))
        parse_ms = int((time.time() - parse_started_at) * 1000)

        return {
            "success": True,
            "corrected_text": corrected_text or text,
            "tags": normalized_tags,
            "knowledge_tags": normalized_tags,
            "question_type": _normalize_question_type(result.get("question_type")) if include_metadata else "unknown",
            "difficulty": difficulty,
            "metadata_warning": metadata_warning,
            "cost_seconds": round(time.time() - started_at, 2),
            "_perf": {"prompt_ms": prompt_ms, "api_ms": api_ms, "parse_ms": parse_ms},
        }

    def evaluate_question_metadata(self, text: str) -> dict[str, Any]:
        return self.analyze(text, include_metadata=True)


nlp_service = NLPService()
