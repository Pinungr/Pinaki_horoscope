import sys
import importlib.util
from tests.test_support import install_engine_dependency_stubs

def pytest_configure(config):
    """
    Ensure stubs are installed before test collection begins,
    but ONLY for modules that are truly missing from the environment.
    """
    for module_name in ["swisseph", "timezonefinder", "pytz"]:
        if importlib.util.find_spec(module_name) is None:
            install_engine_dependency_stubs()
            break
