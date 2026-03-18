import json
import time
from typing import Any

from loguru import logger
from openai import APIConnectionError, APIError, APITimeoutError, AuthenticationError, OpenAI

from app.core.config import settings


LLM_TIMEOUT_SECONDS = 30


def _build_failure(
    error_type: str,
    error: str,
    *,
    detail: str | None = None,
    corrected_text: str = "",
    tags: list[str] | None = None,
    cost_seconds: float = 0.0,
) -> dict[str, Any]:
    return {
        "success": False,
        "corrected_text": corrected_text,
        "tags": tags or [],
        "cost_seconds": round(cost_seconds, 2),
        "error_type": error_type,
        "error": error,
        "detail": detail or error,
    }


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

    def analyze(self, text: str) -> dict[str, Any]:
        if not text:
            return {
                "success": True,
                "corrected_text": "",
                "tags": [],
                "cost_seconds": 0.0,
            }

        if not self.client:
            return _build_failure(
                "service_unavailable",
                "\u667a\u80fd\u6574\u7406\u670d\u52a1\u6682\u65f6\u4e0d\u53ef\u7528",
                detail="deepseek_client_unavailable",
                corrected_text=text,
            )

        started_at = time.time()
        prompt = f"""
You are a high-school math assistant.
Clean OCR mistakes, normalize Markdown and LaTeX, and extract 1-3 knowledge tags.
Return JSON only with the shape:
{{
  "corrected_text": "...",
  "tags": ["...", "..."]
}}

OCR text:
{text}
"""

        try:
            response = self.client.chat.completions.create(
                model=settings.DEEPSEEK_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "Return strict JSON only. Do not wrap the result in markdown fences.",
                    },
                    {"role": "user", "content": prompt},
                ],
                stream=False,
                temperature=0.1,
                max_tokens=2000,
                timeout=LLM_TIMEOUT_SECONDS,
            )
        except APITimeoutError:
            logger.warning("DeepSeek call timed out")
            return _build_failure(
                "timeout",
                "\u667a\u80fd\u6574\u7406\u8d85\u65f6\uff0c\u5df2\u4fdd\u7559\u539f\u59cb\u8bc6\u522b\u7ed3\u679c",
                detail="deepseek_timeout",
                corrected_text=text,
                cost_seconds=time.time() - started_at,
            )
        except AuthenticationError as exc:
            logger.warning("DeepSeek authentication failed: {}", exc)
            return _build_failure(
                "auth_failed",
                "\u667a\u80fd\u6574\u7406\u670d\u52a1\u8ba4\u8bc1\u5931\u8d25",
                detail=f"deepseek_auth_failed:{exc}",
                corrected_text=text,
                cost_seconds=time.time() - started_at,
            )
        except APIConnectionError as exc:
            logger.warning("DeepSeek connection failed: {}", exc)
            return _build_failure(
                "service_unavailable",
                "\u667a\u80fd\u6574\u7406\u670d\u52a1\u6682\u65f6\u4e0d\u53ef\u7528",
                detail=f"deepseek_connection_failed:{exc}",
                corrected_text=text,
                cost_seconds=time.time() - started_at,
            )
        except APIError as exc:
            logger.warning("DeepSeek API error: {}", exc)
            return _build_failure(
                "service_error",
                "\u667a\u80fd\u6574\u7406\u670d\u52a1\u8c03\u7528\u5931\u8d25",
                detail=f"deepseek_api_error:{exc}",
                corrected_text=text,
                cost_seconds=time.time() - started_at,
            )
        except Exception:
            logger.exception("Unexpected DeepSeek failure")
            return _build_failure(
                "service_error",
                "\u667a\u80fd\u6574\u7406\u670d\u52a1\u8c03\u7528\u5931\u8d25",
                detail="deepseek_unexpected_error",
                corrected_text=text,
                cost_seconds=time.time() - started_at,
            )

        try:
            result_content = response.choices[0].message.content or ""
        except (AttributeError, IndexError, TypeError):
            logger.warning("DeepSeek returned unexpected response shape: {}", response)
            return _build_failure(
                "invalid_response",
                "\u667a\u80fd\u6574\u7406\u670d\u52a1\u8fd4\u56de\u4e86\u5f02\u5e38\u6570\u636e",
                detail=f"deepseek_invalid_choice_shape:{response}",
                corrected_text=text,
                cost_seconds=time.time() - started_at,
            )

        clean_json = result_content.replace("```json", "").replace("```", "").strip()
        if not clean_json:
            logger.warning("DeepSeek returned empty content")
            return _build_failure(
                "invalid_response",
                "\u667a\u80fd\u6574\u7406\u670d\u52a1\u8fd4\u56de\u4e86\u7a7a\u6570\u636e",
                detail="deepseek_empty_content",
                corrected_text=text,
                cost_seconds=time.time() - started_at,
            )

        try:
            result = json.loads(clean_json)
        except json.JSONDecodeError:
            logger.warning("DeepSeek returned non-JSON content: {}", clean_json)
            return _build_failure(
                "invalid_response",
                "\u667a\u80fd\u6574\u7406\u670d\u52a1\u8fd4\u56de\u4e86\u65e0\u6548\u683c\u5f0f",
                detail=f"deepseek_non_json:{clean_json}",
                corrected_text=text,
                cost_seconds=time.time() - started_at,
            )

        corrected_text = result.get("corrected_text", text)
        raw_tags = result.get("tags", [])

        if not isinstance(corrected_text, str):
            logger.warning("DeepSeek corrected_text has invalid type: {}", result)
            return _build_failure(
                "invalid_response",
                "\u667a\u80fd\u6574\u7406\u670d\u52a1\u8fd4\u56de\u4e86\u5f02\u5e38\u7ed3\u6784",
                detail=f"deepseek_invalid_corrected_text:{result}",
                corrected_text=text,
                cost_seconds=time.time() - started_at,
            )

        if not isinstance(raw_tags, list):
            logger.warning("DeepSeek tags has invalid type: {}", result)
            return _build_failure(
                "invalid_response",
                "\u667a\u80fd\u6574\u7406\u670d\u52a1\u8fd4\u56de\u4e86\u5f02\u5e38\u7ed3\u6784",
                detail=f"deepseek_invalid_tags:{result}",
                corrected_text=text,
                cost_seconds=time.time() - started_at,
            )

        normalized_tags: list[str] = []
        for tag in raw_tags:
            if isinstance(tag, str) and tag.strip():
                normalized_tags.append(tag.strip())
                continue
            if isinstance(tag, dict) and isinstance(tag.get("label"), str) and tag["label"].strip():
                normalized_tags.append(tag["label"].strip())
                continue
            logger.warning("DeepSeek tag item has invalid shape: {}", tag)
            return _build_failure(
                "invalid_response",
                "\u667a\u80fd\u6574\u7406\u670d\u52a1\u8fd4\u56de\u4e86\u5f02\u5e38\u7ed3\u6784",
                detail=f"deepseek_invalid_tag_item:{tag}",
                corrected_text=text,
                cost_seconds=time.time() - started_at,
            )

        return {
            "success": True,
            "corrected_text": corrected_text or text,
            "tags": normalized_tags,
            "cost_seconds": round(time.time() - started_at, 2),
        }


nlp_service = NLPService()
