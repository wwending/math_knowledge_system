from __future__ import annotations

import inspect
import logging
import sys
from pathlib import Path

from loguru import logger

from app.core.config import settings

DEFAULT_LOG_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
    "{extra[request_id]} | {name}:{function}:{line} - {message}"
)


class InterceptHandler(logging.Handler):
    """Forward stdlib logging records into loguru so every sink stays unified."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = inspect.currentframe(), 0
        while frame and (depth == 0 or frame.f_code.co_filename == logging.__file__):
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def _intercept_std_logging() -> None:
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        std_logger = logging.getLogger(name)
        std_logger.handlers.clear()
        std_logger.propagate = True


def setup_logging(*, log_dir: Path | None = None, level: str | None = None) -> None:
    """Configure stderr + rotating-file sinks; safe to call repeatedly."""
    logger.remove()
    logger.configure(extra={"request_id": "-"})
    resolved_level = level or settings.LOG_LEVEL_NORMALIZED

    logger.add(sys.stderr, format=DEFAULT_LOG_FORMAT, level=resolved_level)

    target_dir = Path(log_dir) if log_dir else settings.LOG_DIR_PATH
    target_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        target_dir / "app.log",
        format=DEFAULT_LOG_FORMAT,
        level=resolved_level,
        rotation="10 MB",
        retention=10,
        enqueue=True,
        backtrace=False,
        diagnose=False,
    )

    _intercept_std_logging()
