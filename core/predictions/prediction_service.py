from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from app.utils.runtime_paths import resolve_resource


class PredictionService:
    """Loads localized prediction meanings from a key-based JSON registry."""

    DEFAULT_LANGUAGE = "en"

    def __init__(self, meanings_path: Path | None = None) -> None:
        self.meanings_path = meanings_path or resolve_resource("core", "predictions", "meanings.json")
        self._meanings: Dict[str, Dict[str, str]] | None = None

    def get_prediction(self, rule_key: Any, language: str | None = None) -> str:
        normalized_key = str(rule_key or "").strip()
        if not normalized_key:
            return ""

        normalized_language = str(language or self.DEFAULT_LANGUAGE).strip().lower() or self.DEFAULT_LANGUAGE
        meanings = self._load_meanings()
        meaning_entry = meanings.get(normalized_key, {})
        if not isinstance(meaning_entry, dict):
            return ""

        localized_text = meaning_entry.get(normalized_language)
        if localized_text:
            return str(localized_text).strip()

        fallback_text = meaning_entry.get(self.DEFAULT_LANGUAGE)
        if fallback_text:
            return str(fallback_text).strip()

        return ""

    def _load_meanings(self) -> Dict[str, Dict[str, str]]:
        if self._meanings is not None:
            return self._meanings

        try:
            payload = json.loads(self.meanings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}

        if not isinstance(payload, dict):
            payload = {}

        self._meanings = {
            str(key).strip(): value
            for key, value in payload.items()
            if isinstance(value, dict)
        }
        return self._meanings


_default_prediction_service = PredictionService()


def get_prediction(rule_key: Any, language: str | None = None) -> str:
    """Returns a localized prediction meaning for one rule key."""
    return _default_prediction_service.get_prediction(rule_key, language)
