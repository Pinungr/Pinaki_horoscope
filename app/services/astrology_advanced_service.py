import logging
from typing import Any, Dict, List
from app.config.config_loader import get_astrology_config_loader
from app.models.domain import ChartData
from app.engine.dasha import DashaEngine
from app.engine.navamsha import NavamshaEngine
from app.utils.cache import get_astrology_cache
from app.utils.safe_execution import execute_safely
from app.utils.logger import log_calculation_step
from core.engines.aspect_engine import calculate_aspects


logger = logging.getLogger(__name__)

class AstrologyAdvancedService:
    """Service layer coordinating advanced astrological math engines."""

    def __init__(self):
        self.dasha_engine = DashaEngine()
        self.navamsha_engine = NavamshaEngine()
        self.cache = get_astrology_cache()
        self.config_loader = get_astrology_config_loader()
        self._unified_engine = None

    def _get_unified_engine(self):
        if self._unified_engine is None:
            from core.engines import create_default_unified_engine
            from app.services.app_settings_service import AppSettingsService
            from app.services.openai_refiner_service import OpenAIRefinerService

            settings_service = AppSettingsService()
            ai_refiner = OpenAIRefinerService(settings_service)
            self._unified_engine = create_default_unified_engine(ai_refiner=ai_refiner)
        return self._unified_engine

    def _is_unified_engine_enabled(self) -> bool:
        return bool(self.config_loader.get("enable_unified_engine", True))

    def generate_advanced_data(self, chart_data_models: List[ChartData], user_dob: str) -> Dict[str, Any]:
        """
        Coordinates the Aspects, Dasha, and Navamsha engines.
        Returns a master dictionary containing all three advanced analysis sets.
        """
        log_calculation_step("advanced_analysis_started", chart_points=len(chart_data_models), user_dob=user_dob)
        user_id = chart_data_models[0].user_id if chart_data_models else 0
        if user_id:
            cached_advanced = self.cache.get("advanced_data", user_id)
            if cached_advanced is not None:
                logger.info("Advanced analysis cache hit for user %s.", user_id)
                return cached_advanced

        # 1. Transpile domain models to the dictionary shapes expected by engines
        # Navamsha input: {"Planet": {"sign": "Aries", "degree": 15.5}}
        navamsha_input = {cd.planet_name: {"sign": cd.sign, "degree": cd.degree} for cd in chart_data_models}
        
        # Dasha input: Moon's absolute degree
        # Absolute degree is (SignIndex - 1) * 30 + local_degree
        signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
                 "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
        
        moon_absolute_longitude = 0.0
        for cd in chart_data_models:
            if cd.planet_name == "Moon":
                try:
                    sign_idx = signs.index(cd.sign)
                except ValueError:
                    sign_idx = 0
                moon_absolute_longitude = (sign_idx * 30.0) + cd.degree
                break

        # 2. Execute engines
        aspects_output = execute_safely(
            lambda: calculate_aspects(chart_data_models),
            logger=logger,
            operation_name="Aspects calculation",
            user_message="Advanced aspect analysis is unavailable right now.",
            fallback=[],
        )
        navamsha_output = execute_safely(
            lambda: self.navamsha_engine.calculate_navamsha(navamsha_input),
            logger=logger,
            operation_name="Navamsha calculation",
            user_message="Navamsha analysis is unavailable right now.",
            fallback={},
        )
        dasha_output = execute_safely(
            lambda: self.dasha_engine.calculate_dasha(moon_absolute_longitude, user_dob),
            logger=logger,
            operation_name="Dasha calculation",
            user_message="Dasha analysis is unavailable right now.",
            fallback=[],
        )

        # Step 17: Enhance Dasha with Event Detection Tags
        from app.engine.event_detector import EventDetectorEngine
        event_detector = EventDetectorEngine()
        dasha_output = execute_safely(
            lambda: event_detector.detect_events(dasha_output, chart_data_models),
            logger=logger,
            operation_name="Timeline event detection",
            user_message="Timeline event detection is unavailable right now.",
            fallback=dasha_output,
        )

        # Step 18: Execute all dynamic user-plugins seamlessly
        from app.plugins.plugin_manager import PluginManager
        from app.models.domain import User
        # Reconstruct a generic user stub for dob requirement (since we only have chart models explicitly passed here)
        user_stub = User(id=chart_data_models[0].user_id if chart_data_models else 0, dob=user_dob, name="", tob="", place="", latitude=0.0, longitude=0.0)
        plugin_manger = PluginManager()
        plugins_output = execute_safely(
            lambda: plugin_manger.execute_all(chart_data_models, user_stub),
            logger=logger,
            operation_name="Plugin execution",
            user_message="Plugin analysis is unavailable right now.",
            fallback={},
        )
        unified_output: Dict[str, Any] = {}
        if self._is_unified_engine_enabled():
            engine = self._get_unified_engine()
            unified_output = execute_safely(
                lambda: (
                    engine.generate_full_analysis(chart_data_models, dob=user_dob, language="en")
                    if hasattr(engine, "generate_full_analysis")
                    else engine.analyze(chart_data_models, dob=user_dob, language="en")
                ),
                logger=logger,
                operation_name="Unified astrology analysis",
                user_message="Unified astrology analysis is unavailable right now.",
                fallback={},
            )

        # 3. Compile Master Output
        advanced_payload = {
            "aspects": aspects_output,
            "navamsha": navamsha_output,
            "dasha": dasha_output,
            "plugins": plugins_output,
            "unified": unified_output,
        }
        if user_id:
            self.cache.set("advanced_data", user_id, advanced_payload)
        return advanced_payload
