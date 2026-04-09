from __future__ import annotations

import logging
import threading
from typing import Any, Callable, List, TypeVar, Optional


T = TypeVar("T")


class FailureRegistry:
    """Thread-local storage for tracking non-fatal service failures."""
    def __init__(self):
        self._local = threading.local()

    def _ensure_init(self):
        if not hasattr(self._local, "failures"):
            self._local.failures = []

    def record(self, operation_name: str, message: str):
        self._ensure_init()
        self._local.failures.append({"operation": operation_name, "message": message})

    def get_failures(self) -> List[dict]:
        self._ensure_init()
        return list(self._local.failures)

    def clear(self):
        self._local.failures = []


# Global instance for easy access across the app
failure_registry = FailureRegistry()


class AppError(Exception):
    """Application-safe exception that carries a user-friendly message."""

    def __init__(self, user_message: str, *, log_message: str | None = None):
        super().__init__(user_message)
        self.user_message = user_message
        self.log_message = log_message or user_message


def execute_safely(
    operation: Callable[[], T],
    *,
    logger: logging.Logger | None = None,
    operation_name: str,
    user_message: str,
    fallback: T | Callable[[], T] | None = None,
    raise_app_error: bool = False,
    record_failure: bool = True,
) -> T:
    """
    Executes an operation with consistent logging and fallback behavior.

    When ``raise_app_error`` is True, failures become ``AppError`` instances.
    When ``record_failure`` is True, non-fatal errors are logged in FailureRegistry.
    """
    try:
        return operation()
    except AppError:
        raise
    except Exception as exc:
        active_logger = logger or logging.getLogger(__name__)
        active_logger.exception("%s failed: %s", operation_name, exc)

        if record_failure:
            failure_registry.record(operation_name, user_message)

        if raise_app_error:
            raise AppError(user_message, log_message=f"{operation_name} failed") from exc

        if callable(fallback):
            return fallback()
        return fallback  # type: ignore[return-value]
