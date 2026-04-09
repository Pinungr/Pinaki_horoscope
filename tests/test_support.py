from __future__ import annotations

import os
import sys
import types
import uuid
from pathlib import Path


def get_engine_dependency_stubs() -> dict[str, types.ModuleType]:
    """Returns a dictionary of lightweight stubs for engine dependencies."""
    # Create Swisseph stub
    swisseph_stub = types.ModuleType("swisseph")
    swisseph_stub.SIDM_LAHIRI = 1
    swisseph_stub.SIDM_RAMAN = 2
    swisseph_stub.SIDM_KRISHNAMURTI = 3
    swisseph_stub.GREG_CAL = 1
    swisseph_stub.CALC_SET = 0
    swisseph_stub.FLG_SWIEPH = 2
    swisseph_stub.FLG_SIDEREAL = 64
    # Planet constants
    swisseph_stub.SUN = 0
    swisseph_stub.MOON = 1
    swisseph_stub.MERCURY = 2
    swisseph_stub.VENUS = 3
    swisseph_stub.MARS = 4
    swisseph_stub.JUPITER = 5
    swisseph_stub.SATURN = 6
    swisseph_stub.URANUS = 7
    swisseph_stub.NEPTUNE = 8
    swisseph_stub.PLUTON = 9
    swisseph_stub.MEAN_NODE = 10
    swisseph_stub.TRUE_NODE = 11
    swisseph_stub.RAHU = 11
    swisseph_stub.KETU = 12

    swisseph_stub.set_sid_mode = lambda *args, **kwargs: None
    swisseph_stub.set_ephe_path = lambda *args, **kwargs: None
    
    def _julday_stub(y, m, d, h=12.0):
        return 1721425.5 + 365*y + 31*m + d + h/24.0
    swisseph_stub.julday = _julday_stub
    
    def _utc_to_jd_stub(y, m, d, h, mi, s, *args):
        return (2460000.0, _julday_stub(y, m, d, h + mi/60.0 + s/3600.0))
    swisseph_stub.utc_to_jd = _utc_to_jd_stub
    swisseph_stub.calc_ut = _mock_calc_ut
    swisseph_stub.houses_ex = lambda *args, **kwargs: ([0.0] * 12, [0.0] * 8)
    swisseph_stub.get_ayanamsa_ut = lambda *args, **kwargs: 0.0

    # Create TimezoneFinder stub
    tf_stub = types.ModuleType("timezonefinder")
    class TimezoneFinder:
        def timezone_at(self, **kwargs): return "UTC"
    tf_stub.TimezoneFinder = TimezoneFinder

    # Create Pytz stub
    pytz_stub = types.ModuleType("pytz")
    import datetime
    
    class _UTC(datetime.tzinfo):
        def utcoffset(self, dt): return datetime.timedelta(0)
        def dst(self, dt): return datetime.timedelta(0)
        def tzname(self, dt): return "UTC"
        def localize(self, dt, is_dst=None):
            if dt.tzinfo is not None: return dt
            return dt.replace(tzinfo=self)
        def normalize(self, dt): return dt
        def __repr__(self): return "<UTC>"
        def __str__(self): return "UTC"

    utc_instance = _UTC()
    pytz_stub.utc = utc_instance
    pytz_stub.timezone = lambda name: utc_instance
    pytz_stub.UTC = utc_instance

    return {
        "swisseph": swisseph_stub,
        "timezonefinder": tf_stub,
        "pytz": pytz_stub,
    }

def install_engine_dependency_stubs() -> None:
    """DEPRECATED: Use get_engine_dependency_stubs() with patch.dict instead."""
    stubs = get_engine_dependency_stubs()
    for name, mod in stubs.items():
        if name not in sys.modules:
            sys.modules[name] = mod


def _mock_calc_ut(jd_ut, planet, flags=0):
    """Returns fake but distinct longitudes to satisfy house/aspect tests."""
    # planet is the second argument in swe.calc_ut(jd_ut, p_idx, flags)
    positions = {
        0: 0.0,    # Sun
        1: 0.0,    # Moon
        5: 120.0,  # Jupiter
    }
    
    # Differentiate Saturn based on test cases (Test A: Pisces house 12; Test B: Aquarius house 1)
    if planet == 6: # Saturn
        # test_relative_house_calculation uses datetime(2026, 1, 1) -> JD ~ 2460946.5
        # test_sade_sati_logic_in_engine uses datetime(2024, 1, 1) -> JD ~ 2460310.5
        if 2460900 < jd_ut < 2461100:
            return ((335.0, 0.0, 0.0, 0.0, 0.0, 0.0), 0) # Pisces (index 11)
        if 2460300 < jd_ut < 2460450:
            return ((315.0, 0.0, 0.0, 0.0, 0.0, 0.0), 0) # Aquarius (index 10)
        
        # TestCoreActivations might use any current date
        return ((305.0, 0.0, 0.0, 0.0, 0.0, 0.0), 0) # Default for other tests

    lon = positions.get(planet, 0.0)
    return ((lon, 0.0, 0.0, 0.0, 0.0, 0.0), 0)


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
