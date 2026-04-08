from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from app.utils.runtime_paths import resolve_resource


class LanguageManager:
    """
    Lightweight translation loader with cached JSON payloads.

    Responsibilities:
    - load one language file by code
    - provide dot-key lookup via get_text("ui.name")
    - fall back to English when a language or key is missing
    """

    DEFAULT_LANGUAGE = "en"

    def __init__(self, language_code: str = DEFAULT_LANGUAGE, translations_dir: Path | None = None) -> None:
        self.translations_dir = translations_dir or resolve_resource("app", "data", "translations")
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._fallback_payload = self._load_payload(self.DEFAULT_LANGUAGE)
        self.current_language = self.DEFAULT_LANGUAGE
        self._active_payload = self._fallback_payload
        self.set_language(language_code)

    def set_language(self, language_code: str) -> None:
        """Activates a language code, falling back to English if unavailable."""
        normalized = str(language_code or self.DEFAULT_LANGUAGE).strip().lower() or self.DEFAULT_LANGUAGE
        payload = self._load_payload(normalized)
        if not payload:
            normalized = self.DEFAULT_LANGUAGE
            payload = self._fallback_payload

        self.current_language = normalized
        self._active_payload = payload

    def get_text(self, key: str) -> str:
        """
        Returns translated text for a dot-notated key.

        Lookup order:
        1. active language
        2. English fallback
        3. final key string
        """
        normalized_key = str(key or "").strip()
        if not normalized_key:
            return ""

        active_value = self._resolve_key(self._active_payload, normalized_key)
        if active_value is not None:
            return active_value

        fallback_value = self._resolve_key(self._fallback_payload, normalized_key)
        if fallback_value is not None:
            return fallback_value

        return normalized_key

    def get_language_meta(self) -> Dict[str, str]:
        """Returns the current language metadata for UI display."""
        meta = self._active_payload.get("meta", {})
        return {
            "code": str(meta.get("code", self.current_language)),
            "native_name": str(meta.get("native_name", self.current_language)),
        }

    def _load_payload(self, language_code: str) -> Dict[str, Any]:
        if language_code in self._cache:
            return self._cache[language_code]

        file_path = self.translations_dir / f"{language_code}.json"
        if not file_path.exists():
            self._cache[language_code] = {}
            return {}

        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = {}

        if not isinstance(payload, dict):
            payload = {}

        self._cache[language_code] = payload
        return payload

    def _resolve_key(self, payload: Dict[str, Any], key: str) -> str | None:
        current: Any = payload
        for part in key.split("."):
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]

        if current is None:
            return None

        return str(current)
