from __future__ import annotations

import logging
from typing import Any, Callable, TypeVar


T = TypeVar("T")


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
) -> T:
    """
    Executes an operation with consistent logging and fallback behavior.

    When ``raise_app_error`` is True, failures become ``AppError`` instances for
    UI-safe presentation. Otherwise, the provided fallback is returned.
    """
    try:
        return operation()
    except AppError:
        raise
    except Exception as exc:
        active_logger = logger or logging.getLogger(__name__)
        active_logger.exception("%s failed: %s", operation_name, exc)

        if raise_app_error:
            raise AppError(user_message, log_message=f"{operation_name} failed") from exc

        if callable(fallback):
            return fallback()
        return fallback  # type: ignore[return-value]
