from __future__ import annotations

import re
import time
import uuid

from loguru import logger
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


def sanitize_request_id(raw: str | None) -> str | None:
    if raw is None:
        return None
    candidate = raw.strip()
    if not candidate:
        return None
    return candidate if _REQUEST_ID_PATTERN.fullmatch(candidate) else None


class RequestContextMiddleware:
    """Attach an X-Request-ID to every request and tag all log lines with it."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming_raw = None
        for key, value in scope.get("headers") or []:
            if key == b"x-request-id":
                incoming_raw = value.decode("latin-1")
                break
        request_id = sanitize_request_id(incoming_raw) or new_request_id()

        state = scope.setdefault("state", {})
        state["request_id"] = request_id

        status_holder: dict[str, int] = {"status": 0}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                headers = list(message.get("headers") or [])
                headers.append((b"x-request-id", request_id.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        started = time.perf_counter()
        failed = False
        with logger.contextualize(request_id=request_id):
            try:
                await self.app(scope, receive, send_wrapper)
            except Exception:
                failed = True
                raise
            finally:
                elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
                status_text = status_holder["status"] or (500 if failed else "-")
                logger.info(
                    "[Access] method={} path={} status={} elapsed_ms={}ms",
                    scope.get("method"),
                    scope.get("path"),
                    status_text,
                    elapsed_ms,
                )
