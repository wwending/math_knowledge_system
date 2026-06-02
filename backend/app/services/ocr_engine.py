import base64
import time
from typing import Any

import requests
from loguru import logger

from app.core.config import settings


OCR_TIMEOUT_SECONDS = 30
OCR_TOKEN_TIMEOUT_SECONDS = 15


def _build_failure(
    error_type: str,
    error: str,
    *,
    detail: str | None = None,
    content: str = "",
    cost_seconds: float = 0.0,
) -> dict[str, Any]:
    return {
        "success": False,
        "content": content,
        "cost_seconds": round(cost_seconds, 2),
        "error_type": error_type,
        "error": error,
        "detail": detail or error,
    }


class OCREngine:
    def __init__(self):
        self.api_key = settings.BAIDU_API_KEY
        self.secret_key = settings.BAIDU_SECRET_KEY
        self.access_token = None
        self.ocr_url = "https://aip.baidubce.com/rest/2.0/ocr/v1/formula"
        self.token_url = "https://aip.baidubce.com/oauth/2.0/token"

        if not self.api_key or not self.secret_key:
            logger.warning("Baidu OCR credentials are not configured")

    def initialize(self):
        try:
            token_result = self.fetch_token()
            if token_result["success"]:
                self.access_token = token_result["access_token"]
                logger.success("Baidu OCR initialized")
            else:
                logger.error(
                    "Baidu OCR initialize failed type={} detail={}",
                    token_result["error_type"],
                    token_result["detail"],
                )
        except Exception:
            logger.exception("Unexpected Baidu OCR initialization failure")

    def fetch_token(self) -> dict[str, Any]:
        if not self.api_key or not self.secret_key:
            return _build_failure(
                "auth_failed",
                "\u6587\u5b57\u8bc6\u522b\u670d\u52a1\u672a\u6b63\u786e\u914d\u7f6e",
                detail="missing_baidu_credentials",
            )

        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key,
        }

        try:
            response = requests.post(
                self.token_url,
                params=params,
                timeout=OCR_TOKEN_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()
        except requests.Timeout:
            return _build_failure(
                "timeout",
                "\u6587\u5b57\u8bc6\u522b\u670d\u52a1\u8fde\u63a5\u8d85\u65f6",
                detail="baidu_token_timeout",
            )
        except requests.RequestException as exc:
            logger.warning("Baidu OCR token request failed: {}", exc)
            return _build_failure(
                "auth_failed",
                "\u6587\u5b57\u8bc6\u522b\u670d\u52a1\u8ba4\u8bc1\u5931\u8d25",
                detail=f"baidu_token_http_error:{exc}",
            )
        except ValueError:
            return _build_failure(
                "invalid_response",
                "\u6587\u5b57\u8bc6\u522b\u670d\u52a1\u8fd4\u56de\u4e86\u65e0\u6548\u8ba4\u8bc1\u6570\u636e",
                detail="baidu_token_invalid_json",
            )

        access_token = data.get("access_token")
        if not access_token:
            logger.warning("Baidu OCR token response missing access_token: {}", data)
            return _build_failure(
                "auth_failed",
                "\u6587\u5b57\u8bc6\u522b\u670d\u52a1\u8ba4\u8bc1\u5931\u8d25",
                detail=f"baidu_token_missing_access_token:{data}",
            )

        return {"success": True, "access_token": access_token}

    def recognize(self, image_path: str) -> dict[str, Any]:
        started_at = time.time()

        if not self.access_token:
            token_result = self.fetch_token()
            if not token_result["success"]:
                token_result["cost_seconds"] = round(time.time() - started_at, 2)
                return token_result
            self.access_token = token_result["access_token"]

        try:
            with open(image_path, "rb") as file_obj:
                img_data = file_obj.read()
        except OSError as exc:
            logger.warning("Failed to read OCR image {}: {}", image_path, exc)
            return _build_failure(
                "service_error",
                "\u4e0a\u4f20\u56fe\u7247\u8bfb\u53d6\u5931\u8d25",
                detail=f"image_read_failed:{exc}",
                cost_seconds=time.time() - started_at,
            )

        request_url = f"{self.ocr_url}?access_token={self.access_token}"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "image": base64.b64encode(img_data).decode(),
            "detect_direction": "true",
            "recognize_granularity": "big",
        }

        try:
            logger.info("Calling Baidu OCR for {}", image_path)
            response = requests.post(
                request_url,
                data=data,
                headers=headers,
                timeout=OCR_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            result_json = response.json()
        except requests.Timeout:
            logger.warning("Baidu OCR timeout for {}", image_path)
            return _build_failure(
                "timeout",
                "\u6587\u5b57\u8bc6\u522b\u8d85\u65f6\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5",
                detail="baidu_ocr_timeout",
                cost_seconds=time.time() - started_at,
            )
        except requests.RequestException as exc:
            logger.warning("Baidu OCR request failed for {}: {}", image_path, exc)
            return _build_failure(
                "service_error",
                "\u6587\u5b57\u8bc6\u522b\u670d\u52a1\u8c03\u7528\u5931\u8d25",
                detail=f"baidu_ocr_http_error:{exc}",
                cost_seconds=time.time() - started_at,
            )
        except ValueError:
            logger.warning("Baidu OCR returned invalid JSON for {}", image_path)
            return _build_failure(
                "invalid_response",
                "\u6587\u5b57\u8bc6\u522b\u670d\u52a1\u8fd4\u56de\u4e86\u65e0\u6548\u6570\u636e",
                detail="baidu_ocr_invalid_json",
                cost_seconds=time.time() - started_at,
            )

        if "error_code" in result_json:
            error_code = result_json.get("error_code")
            error_msg = result_json.get("error_msg", "unknown_error")
            logger.warning("Baidu OCR API error code={} msg={}", error_code, error_msg)
            if error_code in {110, 111}:
                self.access_token = None
                token_result = self.fetch_token()
                if token_result["success"]:
                    self.access_token = token_result["access_token"]
                    return self.recognize(image_path)
                token_result["cost_seconds"] = round(time.time() - started_at, 2)
                return token_result

            error_type = "auth_failed" if error_code in {6, 14, 17, 18, 19, 216201} else "service_error"
            return _build_failure(
                error_type,
                "\u6587\u5b57\u8bc6\u522b\u670d\u52a1\u8fd4\u56de\u4e86\u9519\u8bef",
                detail=f"baidu_ocr_api_error:{error_code}:{error_msg}",
                cost_seconds=time.time() - started_at,
            )

        words_result = result_json.get("words_result")
        if not isinstance(words_result, list):
            logger.warning("Baidu OCR words_result has invalid shape: {}", result_json)
            return _build_failure(
                "invalid_response",
                "\u6587\u5b57\u8bc6\u522b\u670d\u52a1\u8fd4\u56de\u4e86\u5f02\u5e38\u6570\u636e",
                detail=f"baidu_ocr_invalid_words_result:{result_json}",
                cost_seconds=time.time() - started_at,
            )

        lines = [item.get("words", "").strip() for item in words_result if isinstance(item, dict)]
        final_content = "\n\n".join(line for line in lines if line)
        if not final_content.strip():
            logger.warning("Baidu OCR returned empty content for {}", image_path)
            return _build_failure(
                "empty_result",
                "\u672a\u80fd\u8bc6\u522b\u5230\u53ef\u7528\u6587\u5b57\uff0c\u8bf7\u66f4\u6362\u66f4\u6e05\u6670\u7684\u56fe\u7247\u540e\u91cd\u8bd5",
                detail="baidu_ocr_empty_result",
                cost_seconds=time.time() - started_at,
            )

        logger.success("Baidu OCR succeeded for {}", image_path)
        return {
            "success": True,
            "content": final_content,
            "cost_seconds": round(time.time() - started_at, 2),
        }


ocr_service = OCREngine()
