import os
import importlib
import inspect
import logging
from typing import List, Dict, Any
from app.models.domain import ChartData, User
from app.plugins.base_plugin import AstrologyPlugin


logger = logging.getLogger(__name__)

class PluginManager:
    """Dynamically loads and executes external astrology modules."""

    def __init__(self):
        self.plugins: List[AstrologyPlugin] = []
        self._load_plugins()

    def _load_plugins(self):
        """Scans the plugins directory and auto-registers valid plugin classes."""
        plugin_dir = os.path.dirname(__file__)
        package_name = "app.plugins"

        import sys
        if package_name not in sys.modules:
            # We are initializing for the first time
            pass
            
        for filename in os.listdir(plugin_dir):
            if filename.endswith(".py") and filename not in ("__init__.py", "base_plugin.py", "plugin_manager.py"):
                module_name = filename[:-3]
                full_module_name = f"{package_name}.{module_name}"
                try:
                    module = importlib.import_module(full_module_name)
                    # Find classes in the module that inherit from AstrologyPlugin
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, AstrologyPlugin) and obj is not AstrologyPlugin:
                            # Instantiate and register
                            self.plugins.append(obj())
                            logger.info("Plugin loaded: %s", obj.__name__)
                except Exception as e:
                    logger.warning("Failed to load plugin %s: %s", module_name, e)

    def execute_all(self, chart_data: List[ChartData], user: User) -> Dict[str, Any]:
        """Runs all registered plugins and aggregates their output."""
        aggregated_results = {}
        for plugin in self.plugins:
            try:
                logger.info("Executing plugin: %s", plugin.get_plugin_name())
                result = plugin.process(chart_data, user)
                aggregated_results[plugin.get_plugin_name()] = result
            except Exception as e:
                logger.error("Plugin %s crashed during execution: %s", plugin.get_plugin_name(), e)
                aggregated_results[plugin.get_plugin_name()] = {"error": str(e)}

        return aggregated_results
