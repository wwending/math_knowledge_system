from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger

from app.core.request_context import REQUEST_ID_HEADER, new_request_id

INTERNAL_ERROR_MESSAGE = "服务端处理失败，请稍后重试或联系管理员。"


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception method={} path={}", request.method, request.url.path)
    request_id = getattr(request.state, "request_id", None) or new_request_id()
    return JSONResponse(
        status_code=500,
        content={"detail": INTERNAL_ERROR_MESSAGE, "request_id": request_id},
        headers={REQUEST_ID_HEADER: request_id},
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(Exception, unhandled_exception_handler)
