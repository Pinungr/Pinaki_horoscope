from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any
from app.utils.runtime_paths import ensure_runtime_dir


DEFAULT_LOGGER_NAME = "horoscope"
_IS_CONFIGURED = False


def _format_context(context: dict[str, Any]) -> str:
    """Builds a compact key=value suffix for structured log details."""
    if not context:
        return ""

    parts = []
    for key, value in context.items():
        if value is None:
            continue
        parts.append(f"{key}={value!r}")
    return " | " + ", ".join(parts) if parts else ""


def setup_logging(
    *,
    log_level: int = logging.INFO,
    log_dir: str | Path | None = None,
    logger_name: str = DEFAULT_LOGGER_NAME,
) -> logging.Logger:
    """
    Configures application logging once with console and rotating file handlers.
    """
    global _IS_CONFIGURED

    app_logger = logging.getLogger(logger_name)
    if _IS_CONFIGURED:
        return app_logger

    resolved_log_dir = Path(log_dir) if log_dir is not None else ensure_runtime_dir("logs")
    resolved_log_dir.mkdir(parents=True, exist_ok=True)
    log_file = resolved_log_dir / "horoscope.log"

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=1_048_576,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    app_logger.setLevel(log_level)
    app_logger.info("Logging initialized.%s", _format_context({"log_file": str(log_file)}))
    _IS_CONFIGURED = True
    return app_logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Returns a logger instance for a module or the application."""
    return logging.getLogger(name or DEFAULT_LOGGER_NAME)


def log_user_action(action: str, **context: Any) -> None:
    """Logs a user-initiated UI or service action."""
    get_logger(DEFAULT_LOGGER_NAME).info("User action: %s%s", action, _format_context(context))


def log_rule_match(rule_id: Any = None, result_text: str | None = None, **context: Any) -> None:
    """Logs a matched astrology rule for later traceability."""
    payload = {"rule_id": rule_id, "result_text": result_text, **context}
    get_logger(DEFAULT_LOGGER_NAME).info("Rule matched%s", _format_context(payload))


def log_calculation_step(step: str, **context: Any) -> None:
    """Logs major engine calculation milestones."""
    get_logger(DEFAULT_LOGGER_NAME).info("Calculation step: %s%s", step, _format_context(context))
