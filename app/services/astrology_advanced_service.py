import logging
from typing import Any, Dict, List
from app.config.config_loader import get_astrology_config_loader
from app.models.domain import ChartData
from core.yoga.models import ChartSnapshot
from app.services.reasoning_service import ReasoningService
from app.engine.dasha import DashaEngine
from app.engine.navamsha import NavamshaEngine
from app.engine.varga_engine import VargaEngine
from app.engine.transit_engine import TransitEngine
from app.engine.shadbala_engine_wrapper import calculate_shadbala
from app.utils.cache import get_astrology_cache
from app.utils.safe_execution import execute_safely
from app.utils.logger import log_calculation_step
from core.engines.aspect_engine import calculate_aspects
from core.predictions.prediction_service import PredictionService
from app.services.timeline_service import TimelineService


logger = logging.getLogger(__name__)

class AstrologyAdvancedService:
    """Service layer coordinating advanced astrological math engines."""

    def __init__(self):
        self.dasha_engine = DashaEngine()
        self.navamsha_engine = NavamshaEngine()
        self.varga_engine = VargaEngine()
        self.transit_engine = TransitEngine()
        self.prediction_service = PredictionService()
        self.reasoning_service = ReasoningService()
        self.timeline_service = TimelineService()
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

    def generate_advanced_data(
        self,
        chart_data_models: List[ChartData],
        user_dob: str,
        *,
        language: str = "en",
    ) -> Dict[str, Any]:
        """
        Coordinates the Aspects, Dasha, and Navamsha engines.
        Returns a master dictionary containing all three advanced analysis sets.
        """
        log_calculation_step("advanced_analysis_started", chart_points=len(chart_data_models), user_dob=user_dob)
        normalized_language = str(language or "en").strip().lower() or "en"
        user_id = chart_data_models[0].user_id if chart_data_models else 0
        if user_id:
            cached_advanced = self.cache.get("advanced_data", user_id)
            if isinstance(cached_advanced, dict):
                cached_language = str(cached_advanced.get("_language", "en")).strip().lower() or "en"
                if cached_language == normalized_language:
                    logger.info("Advanced analysis cache hit for user %s.", user_id)
                    return cached_advanced
            elif cached_advanced is not None and normalized_language == "en":
                logger.info("Advanced analysis cache hit for user %s.", user_id)
                return cached_advanced

        # 1. Transpile domain models to the dictionary shapes expected by engines
        # Navamsha input: {"Planet": {"sign": "Aries", "degree": 15.5}}
        navamsha_input = {cd.planet_name: {"sign": cd.sign, "degree": cd.degree} for cd in chart_data_models}
        
        # Dasha input: Moon's exact astronomical Sidereal absolute longitude
        moon_absolute_longitude = 0.0
        for cd in chart_data_models:
            if cd.planet_name == "Moon":
                moon_absolute_longitude = getattr(cd, "absolute_longitude", 0.0)
                break

        # 2. Execute engines
        aspects_output = execute_safely(
            lambda: calculate_aspects(chart_data_models),
            logger=logger,
            operation_name="Aspects calculation",
            user_message="Advanced aspect analysis is unavailable right now.",
            fallback=[],
            raise_app_error=True,
        )
        navamsha_output = execute_safely(
            lambda: self.navamsha_engine.calculate_navamsha(navamsha_input),
            logger=logger,
            operation_name="Navamsha calculation",
            user_message="Navamsha analysis is unavailable right now.",
            fallback={},
            raise_app_error=True,
        )
        dasha_output = execute_safely(
            lambda: self.dasha_engine.calculate_dasha(moon_absolute_longitude, user_dob),
            logger=logger,
            operation_name="Dasha calculation",
            user_message="Dasha analysis is unavailable right now.",
            fallback=[],
            raise_app_error=True,
        )
        shastiamsha_output = execute_safely(
            lambda: self.varga_engine.calculate_varga_chart(60, chart_data_models),
            logger=logger,
            operation_name="Shastiamsha (D60) calculation",
            user_message="D60 analysis is unavailable right now.",
            fallback={},
        )
        dashamsha_output = execute_safely(
            lambda: self.varga_engine.get_d10_chart(chart_data_models),
            logger=logger,
            operation_name="Dashamsha (D10) calculation",
            user_message="D10 analysis is unavailable right now.",
            fallback={"ascendant_sign": "", "rows": [], "placements": {}},
        )
        d10_career_validation = execute_safely(
            lambda: self.prediction_service.evaluate_d10_career_validation(
                chart_data=chart_data_models,
                prediction_context={"area": "career", "relevant_houses": [10]},
            ),
            logger=logger,
            operation_name="D10 career validation",
            user_message="D10 career validation is unavailable right now.",
            fallback={
                "status": "neutral",
                "factors": ["D10 validation unavailable."],
                "multiplier": 1.0,
                "score": 0.0,
            },
        )
        # Transit calculation with explicit dual references:
        # - Lagna (Ascendant)
        # - Chandra Lagna (Moon)
        transit_output = execute_safely(
            lambda: self.transit_engine.calculate_transits(
                ChartSnapshot.from_rows(chart_data_models),
                reference="both",
            ),
            logger=logger,
            operation_name="Transit (Gochar) calculation",
            user_message="Current transits are unavailable right now.",
            fallback={},
        )
        shadbala_output = execute_safely(
            lambda: calculate_shadbala(chart_data_models),
            logger=logger,
            operation_name="Shadbala calculation",
            user_message="Planetary strength analysis is unavailable right now.",
            fallback={},
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
        timeline_forecast: Dict[str, Any] = {"timeline": []}
        if self._is_unified_engine_enabled():
            engine = self._get_unified_engine()
            unified_output = execute_safely(
                lambda: (
                    engine.generate_full_analysis(chart_data_models, dob=user_dob, language=normalized_language)
                    if hasattr(engine, "generate_full_analysis")
                    else engine.analyze(chart_data_models, dob=user_dob, language=normalized_language)
                ),
                logger=logger,
                operation_name="Unified astrology analysis",
                user_message="Unified astrology analysis is unavailable right now.",
                fallback={},
            )
            if isinstance(unified_output, dict):
                unified_predictions = unified_output.get("predictions", [])
                if isinstance(unified_predictions, list):
                    for row in unified_predictions:
                        if not isinstance(row, dict):
                            continue
                        timing = row.get("timing", {}) if isinstance(row.get("timing"), dict) else {}

                        raw_concordance = timing.get("concordance_score", row.get("concordance_score", 0.5))
                        try:
                            concordance_score = float(raw_concordance)
                        except (TypeError, ValueError):
                            concordance_score = 0.5
                        concordance_score = max(0.0, min(1.0, concordance_score))

                        agreement_level = str(
                            timing.get("agreement_level", row.get("agreement_level", "medium"))
                        ).strip().lower() or "medium"
                        if agreement_level not in {"high", "medium", "low"}:
                            agreement_level = "medium"

                        raw_factors = timing.get("concordance_factors", row.get("concordance_factors", []))
                        concordance_factors = (
                            [str(item).strip() for item in raw_factors if str(item).strip()]
                            if isinstance(raw_factors, list)
                            else []
                        )

                        timing["concordance_score"] = round(concordance_score, 3)
                        timing["agreement_level"] = agreement_level
                        timing["concordance_factors"] = concordance_factors
                        row["timing"] = timing
                        row["concordance_score"] = round(concordance_score, 3)
                        row["agreement_level"] = agreement_level
                        row["concordance_factors"] = concordance_factors

                        if str(row.get("area", "")).strip().lower() != "career":
                            continue
                        d10_status = str(timing.get("d10_status", d10_career_validation.get("status", "neutral"))).strip().lower() or "neutral"
                        d10_evidence_raw = timing.get("d10_evidence", d10_career_validation.get("factors", []))
                        d10_evidence = (
                            [str(item).strip() for item in d10_evidence_raw if str(item).strip()]
                            if isinstance(d10_evidence_raw, list)
                            else [str(item).strip() for item in d10_career_validation.get("factors", []) if str(item).strip()]
                        )

                        timing["d10_status"] = d10_status
                        timing["d10_evidence"] = d10_evidence
                        row["timing"] = timing
                        row["d10_status"] = d10_status
                        row["d10_evidence"] = d10_evidence
                    unified_output["ui_payload"] = self.reasoning_service.build_ui_payload(
                        unified_predictions,
                        summary=unified_output.get("summary", {}),
                        language=normalized_language,
                    )
                    timeline_forecast = execute_safely(
                        lambda: self.timeline_service.build_timeline_forecast(
                            unified_predictions,
                            dasha_output,
                            language=normalized_language,
                        ),
                        logger=logger,
                        operation_name="Unified timeline activation forecast",
                        user_message="Timeline activation forecast is unavailable right now.",
                        fallback={"timeline": []},
                    )
                    unified_output["timeline_forecast"] = timeline_forecast

        # 3. Compile Master Output
        advanced_payload = {
            "aspects": aspects_output,
            "navamsha": navamsha_output,
            "shastiamsha": shastiamsha_output,
            "dashamsha": dashamsha_output,
            "d10_career_validation": d10_career_validation,
            "transits": transit_output,
            "shadbala": shadbala_output,
            "dasha": dasha_output,
            "plugins": plugins_output,
            "unified": unified_output,
            "timeline_forecast": timeline_forecast,
            "_language": normalized_language,
        }
        if user_id:
            self.cache.set("advanced_data", user_id, advanced_payload)
        return advanced_payload
