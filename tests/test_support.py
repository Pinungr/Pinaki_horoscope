from __future__ import annotations

import os
import sys
import types
import uuid
from pathlib import Path


def install_engine_dependency_stubs() -> None:
    """Installs lightweight stubs so service tests can import without native deps."""
    if "swisseph" not in sys.modules:
        swisseph_stub = types.ModuleType("swisseph")
        swisseph_stub.SIDM_LAHIRI = 1
        swisseph_stub.SIDM_RAMAN = 2
        swisseph_stub.SIDM_KRISHNAMURTI = 3
        swisseph_stub.GREG_CAL = 1
        swisseph_stub.CALC_SET = 0
        swisseph_stub.set_sid_mode = lambda *args, **kwargs: None
        swisseph_stub.julday = lambda *args, **kwargs: 0.0
        swisseph_stub.calc_ut = lambda *args, **kwargs: ((0.0, 0.0, 0.0, 0.0, 0.0, 0.0), 0)
        swisseph_stub.houses_ex = lambda *args, **kwargs: ([0.0] * 12, [0.0] * 8)
        swisseph_stub.get_ayanamsa_ut = lambda *args, **kwargs: 0.0
        sys.modules["swisseph"] = swisseph_stub

    if "timezonefinder" not in sys.modules:
        timezonefinder_stub = types.ModuleType("timezonefinder")

        class TimezoneFinder:
            def timezone_at(self, **kwargs):
                return "UTC"

        timezonefinder_stub.TimezoneFinder = TimezoneFinder
        sys.modules["timezonefinder"] = timezonefinder_stub

    if "pytz" not in sys.modules:
        pytz_stub = types.ModuleType("pytz")

        class _UTC:
            def localize(self, dt):
                return dt

            def astimezone(self, tz):
                return dt

        pytz_stub.utc = _UTC()
        pytz_stub.timezone = lambda name: _UTC()
        sys.modules["pytz"] = pytz_stub


def build_temp_db_path(prefix: str) -> str:
    """Builds a unique sqlite file path inside the repo's database folder."""
    database_dir = Path("database")
    database_dir.mkdir(exist_ok=True)
    return str(database_dir / f"{prefix}_{uuid.uuid4().hex}.db")


def cleanup_temp_db(path: str) -> None:
    """Removes a temporary sqlite database when a test finishes."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except PermissionError:
        pass
