"""Lightweight logging helpers for the FastAPI application."""

import logging
import os
from collections import deque
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Any, Deque, Dict, Optional


class StructuredLogger:
    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)

    def _format(self, message: str, extra: Dict[str, Any]) -> str:
        if extra:
            extras = " ".join(f"{key}={value}" for key, value in extra.items())
            return f"{message} | {extras}"
        return message

    def _log(self, level: int, message: str, **kwargs: Any) -> None:
        exc_info = kwargs.pop("exc_info", None)
        formatted = self._format(message, kwargs)
        self._logger.log(level, formatted, exc_info=exc_info)

    def info(self, message: str, **kwargs: Any) -> None:
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self._log(logging.ERROR, message, **kwargs)

    def debug(self, message: str, **kwargs: Any) -> None:
        self._log(logging.DEBUG, message, **kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        self._log(logging.CRITICAL, message, **kwargs)


def setup_production_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    enable_console: bool = True,
) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level.upper())

    if log_file:
        directory = os.path.dirname(log_file)
        if directory:
            os.makedirs(directory, exist_ok=True)
        file_handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3)
        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        root_logger.addHandler(file_handler)

    if enable_console:
        if not any(isinstance(handler, logging.StreamHandler) for handler in root_logger.handlers):
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
            root_logger.addHandler(console_handler)


def get_logger(name: str) -> StructuredLogger:
    return StructuredLogger(name)


class ErrorTracker:
    def __init__(self) -> None:
        self._events: Deque[Dict[str, Any]] = deque(maxlen=500)

    def record_error(self, error: Exception) -> None:
        self._events.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "message": str(error),
            }
        )

    def get_error_summary(self, window_hours: int = 1) -> Dict[str, Any]:
        return {
            "window_hours": window_hours,
            "total_errors": len(self._events),
            "recent": list(self._events)[-5:],
        }


error_tracker = ErrorTracker()


class SecurityLogger:
    def __init__(self) -> None:
        self._logger = logging.getLogger("security")

    def log_suspicious_input(self, input_type: str, content_sample: str, user_id: str) -> None:
        self._logger.warning(
            "Suspicious input detected",
            extra={
                "input_type": input_type,
                "user_id": user_id,
                "content_sample": content_sample,
            },
        )


security_logger = SecurityLogger()


def get_error_middleware():  # pragma: no cover
    async def middleware(request, call_next):  # type: ignore[override]
        try:
            return await call_next(request)
        except Exception as exc:  # pylint: disable=broad-except
            error_tracker.record_error(exc)
            logging.getLogger("retriever_api").exception("Unhandled exception", exc_info=exc)
            raise

    return middleware
