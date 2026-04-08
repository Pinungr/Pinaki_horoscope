from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

from app.config.settings import CONFIG_DIR


logger = logging.getLogger(__name__)


class AstrologyConfigLoader:
    """
    Loads and caches astrology configuration from disk.

    The loader is intentionally additive and backward compatible:
    - missing files are auto-created with defaults
    - unknown keys are preserved
    - callers can reload or update without restarting the app
    """

    DEFAULTS: Dict[str, Any] = {
        "ayanamsa": "Lahiri",
        "house_system": "whole_sign",
        "timezone_mode": "auto",
        "enable_unified_engine": True,
    }

    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or (CONFIG_DIR / "astrology_config.json")
        self._cached_config: Dict[str, Any] | None = None

    def load(self, *, force_reload: bool = False) -> Dict[str, Any]:
        """Loads the config once and returns a cached normalized copy afterwards."""
        if self._cached_config is not None and not force_reload:
            return dict(self._cached_config)

        self._ensure_exists()

        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read astrology config from %s: %s. Falling back to defaults.", self.config_path, exc)
            payload = {}

        normalized = dict(self.DEFAULTS)
        if isinstance(payload, dict):
            normalized.update(payload)

        normalized["ayanamsa"] = str(normalized.get("ayanamsa", self.DEFAULTS["ayanamsa"])).strip() or self.DEFAULTS["ayanamsa"]
        normalized["house_system"] = str(normalized.get("house_system", self.DEFAULTS["house_system"])).strip() or self.DEFAULTS["house_system"]
        normalized["timezone_mode"] = str(normalized.get("timezone_mode", self.DEFAULTS["timezone_mode"])).strip() or self.DEFAULTS["timezone_mode"]
        raw_unified = normalized.get("enable_unified_engine", self.DEFAULTS["enable_unified_engine"])
        if isinstance(raw_unified, str):
            normalized["enable_unified_engine"] = raw_unified.strip().lower() in {"1", "true", "yes", "on"}
        else:
            normalized["enable_unified_engine"] = bool(raw_unified)

        self._cached_config = normalized
        logger.info("Astrology config loaded from %s.", self.config_path)
        return dict(normalized)

    def get(self, key: str, default: Any = None) -> Any:
        """Returns a single config value using the cached configuration."""
        config = self.load()
        return config.get(key, default)

    def reload(self) -> Dict[str, Any]:
        """Forces the config to be reloaded from disk."""
        return self.load(force_reload=True)

    def update(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Merges updates into config, persists them, and refreshes the cache."""
        current = self.load()
        current.update(updates or {})
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(current, indent=2), encoding="utf-8")
        logger.info("Astrology config updated at %s.", self.config_path)
        self._cached_config = None
        return self.load(force_reload=True)

    def _ensure_exists(self) -> None:
        """Creates the config file with defaults when it is missing."""
        if self.config_path.exists():
            return

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(self.DEFAULTS, indent=2), encoding="utf-8")
        logger.info("Created default astrology config at %s.", self.config_path)


_GLOBAL_LOADER = AstrologyConfigLoader()


def get_astrology_config_loader() -> AstrologyConfigLoader:
    """Returns the shared astrology config loader instance."""
    return _GLOBAL_LOADER


def get_astrology_config(force_reload: bool = False) -> Dict[str, Any]:
    """Returns the shared astrology config dictionary."""
    return _GLOBAL_LOADER.load(force_reload=force_reload)
