from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from app.config.settings import DB_DIR


class AppSettingsService:
    """Persists lightweight desktop settings in a local JSON file."""

    DEFAULTS: Dict[str, Any] = {
        "ai_enabled": False,
        "openai_api_key": "",
        "openai_model": "gpt-5-mini",
        "language_code": "en",
    }

    def __init__(self, settings_path: Path | None = None):
        self.settings_path = settings_path or (DB_DIR / "app_settings.json")

    def load(self) -> Dict[str, Any]:
        """Loads settings from disk, falling back to defaults."""
        if not self.settings_path.exists():
            return dict(self.DEFAULTS)

        try:
            payload = json.loads(self.settings_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return dict(self.DEFAULTS)

        merged = dict(self.DEFAULTS)
        merged.update(payload if isinstance(payload, dict) else {})
        return merged

    def save(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Saves settings to disk and returns the normalized result."""
        normalized = dict(self.DEFAULTS)
        normalized.update(settings or {})
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(
            json.dumps(normalized, indent=2),
            encoding="utf-8",
        )
        return normalized
