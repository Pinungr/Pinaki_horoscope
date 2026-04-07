from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """Returns True when running from a packaged executable."""
    return bool(getattr(sys, "frozen", False))


def get_bundle_root() -> Path:
    """
    Returns the read-only resource root.

    In source mode this is the repository root. In a frozen build this resolves
    to PyInstaller's extraction directory.
    """
    if is_frozen() and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()
    return Path(__file__).resolve().parents[2]


def get_app_root() -> Path:
    """
    Returns the writable application root.

    In source mode this remains the repository root. In a frozen build this is
    the executable directory so database, logs, and config stay beside the app.
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def resolve_resource(*parts: str) -> Path:
    """Builds a path to a bundled read-only resource."""
    return get_bundle_root().joinpath(*parts)


def ensure_runtime_dir(*parts: str) -> Path:
    """Builds and creates a writable runtime directory."""
    target = get_app_root().joinpath(*parts)
    target.mkdir(parents=True, exist_ok=True)
    return target


def get_ephemeris_dir() -> Path | None:
    """
    Resolves the ephemeris directory for offline Swiss Ephemeris calculations.

    Resolution order:
    1. HOROSCOPE_EPHEMERIS_DIR environment variable
    2. writable `<app>/ephemeris`
    3. bundled `app/data/ephemeris`
    """
    configured_path = os.environ.get("HOROSCOPE_EPHEMERIS_DIR", "").strip()
    if configured_path:
        candidate = Path(configured_path).expanduser().resolve()
        return candidate if candidate.exists() else None

    for candidate in (
        get_app_root() / "ephemeris",
        resolve_resource("app", "data", "ephemeris"),
    ):
        if candidate.exists():
            return candidate
    return None
