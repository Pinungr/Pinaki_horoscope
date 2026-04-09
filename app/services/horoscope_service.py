import logging
import json
from typing import Tuple, List, Dict, Any, Optional
from app.repositories.database_manager import DatabaseManager
from app.repositories.user_repo import UserRepository
from app.repositories.chart_repo import ChartRepository
from app.repositories.location_repo import LocationRepository
from app.repositories.rule_repo import RuleRepository
from app.engine.prediction_scorer import score_predictions
from app.engine.rule_engine import RuleEngine
from app.engine.interpreter import InterpreterEngine
from app.engine.shadbala_engine_wrapper import calculate_shadbala, normalize_shadbala_payload
from app.models.domain import User, Rule
from app.utils.cache import get_astrology_cache
from app.utils.logger import log_user_action, log_calculation_step
from app.utils.validators import validate_user_input
from app.utils.safe_execution import AppError, execute_safely, failure_registry
from core.engines.functional_nature import FunctionalNatureEngine
from core.engines.aspect_engine import calculate_aspects
from core.predictions.prediction_service import PredictionService as CorePredictionService

logger = logging.getLogger(__name__)

class HoroscopeService:
    """Orchestrates astrology logic and database persistence."""
    def __init__(self, db_manager: DatabaseManager):
        self.user_repo = UserRepository(db_manager)
        self.chart_repo = ChartRepository(db_manager)
        self.rule_repo = RuleRepository(db_manager)
        self.location_repo = LocationRepository(db_manager)
        self.interpreter = InterpreterEngine()
        self.functional_nature_engine = FunctionalNatureEngine()
        self.prediction_service = CorePredictionService()
        self.cache = get_astrology_cache()

    def get_service_failures(self) -> List[dict]:
        """Returns non-fatal failures captured during the last operation."""
        return failure_registry.get_failures()

    def _hydrate_location_fields(self, user_data: dict) -> dict:
        """Fills latitude/longitude from selected state/city when available."""
        enriched_data = dict(user_data or {})
        state = str(enriched_data.get("state", "")).strip()
        city = str(enriched_data.get("city", "")).strip()
        latitude = enriched_data.get("latitude")
        longitude = enriched_data.get("longitude")

        if state and city:
            location = self.location_repo.get_location(state, city)
            if location and (latitude in {None, ""} or longitude in {None, ""}):
                enriched_data["latitude"] = location["latitude"]
                enriched_data["longitude"] = location["longitude"]

            if not str(enriched_data.get("place", "")).strip():
                enriched_data["place"] = f"{city}, {state}"

        return enriched_data

    def prepare_user_input(self, user_data: dict) -> dict:
        """Enriches and validates raw user input before controller or engine use."""
        validated = validate_user_input(self._hydrate_location_fields(user_data))
        logger.info(
            "Validated user input for name=%s state=%s city=%s.",
            validated.get("name"),
            validated.get("state"),
            validated.get("city"),
        )
        return validated

    @staticmethod
    def _calculate_chart_data(user: User) -> List[Any]:
        """
        Lazily imports the heavy chart calculator dependency at runtime.
        This keeps service imports safe in environments where swisseph is not installed.
        """
        from app.engine.calculator import AstrologyEngine

        return AstrologyEngine().calculate_chart(user)

    @staticmethod
    def _system_prediction(summary: str) -> Dict[str, Dict[str, Any]]:
        """Builds a stable fallback prediction payload for UI consumers."""
        return {
            "system": {
                "score": 0.0,
                "confidence": "low",
                "summary": summary,
                "positive_summary_keys": ["chart_generated_no_rules"],
                "negative_summary_keys": [],
            }
        }

    def _evaluate_chart_predictions(
        self,
        chart_data_models: List[Any],
        *,
        shadbala_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Evaluates rules for an existing chart and returns scored predictions."""
        area_predictions = execute_safely(
            lambda: self.prediction_service.build_bhava_lord_karaka_predictions(chart_data_models),
            logger=logger,
            operation_name="Bhava-lord-karaka area reasoning",
            user_message="Area-based interpretations are unavailable right now.",
            fallback=[],
        )

        rules = execute_safely(
            lambda: self.rule_repo.get_all(),
            logger=logger,
            operation_name="Rule repository fetch",
            user_message="Predictions are unavailable right now.",
            fallback=[],
        )

        raw_predictions: List[Any] = []
        if rules:
            rule_engine = RuleEngine(rules)
            precomputed_aspects = execute_safely(
                lambda: calculate_aspects(chart_data_models),
                logger=logger,
                operation_name="Aspect precomputation for rule evaluation",
                user_message="Predictions are unavailable right now.",
                fallback=[],
            )
            raw_predictions = execute_safely(
                lambda: rule_engine.evaluate(chart_data_models, aspects=precomputed_aspects),
                logger=logger,
                operation_name="Rule engine evaluation",
                user_message="Predictions are unavailable right now.",
                fallback=[],
            )

        combined_predictions: List[Any] = []
        if isinstance(raw_predictions, list):
            combined_predictions.extend(raw_predictions)
        if isinstance(area_predictions, list):
            combined_predictions.extend(area_predictions)

        if not combined_predictions:
            return {}

        normalized_shadbala = self._get_or_calculate_shadbala(
            chart_data_models,
            precomputed=shadbala_payload,
        )

        return execute_safely(
            lambda: self._score_rule_engine_output(
                combined_predictions,
                rules,
                chart_data_models=chart_data_models,
                strength_payload=normalized_shadbala,
            ),
            logger=logger,
            operation_name="Prediction scoring",
            user_message="Predictions are unavailable right now.",
            fallback={},
        )

    def _get_or_calculate_shadbala(
        self,
        chart_data_models: List[Any],
        *,
        precomputed: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Returns normalized Shadbala payload, reusing precomputed values when available."""
        if precomputed is not None:
            return normalize_shadbala_payload(precomputed, chart_data_models)

        calculated = execute_safely(
            lambda: calculate_shadbala(chart_data_models),
            logger=logger,
            operation_name="Shadbala calculation",
            user_message="Planetary strength analysis is unavailable right now.",
            fallback={},
        )
        return normalize_shadbala_payload(calculated, chart_data_models)

    @staticmethod
    def _format_display_data(chart_data_models: List[Any]) -> List[Dict[str, Any]]:
        """Formats chart rows into the stable UI display shape."""
        return [
            {
                "Planet": cd.planet_name,
                "Sign": cd.sign,
                "House": cd.house,
                "Degree": round(cd.degree, 2)
            }
            for cd in chart_data_models
        ]

    def _cache_chart_bundle(
        self,
        user_id: int,
        *,
        display_data: Optional[List[Dict[str, Any]]] = None,
        predictions: Optional[Dict[str, Dict[str, Any]]] = None,
        shadbala: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Stores chart, prediction, and shadbala results for one user when available."""
        if display_data is not None:
            self.cache.set("chart_display", user_id, display_data)
        if predictions is not None:
            self.cache.set("predictions", user_id, predictions)
        if shadbala is not None:
            self.cache.set("shadbala", user_id, normalize_shadbala_payload(shadbala))

    @staticmethod
    def _predictions_are_strength_gated(predictions: Any) -> bool:
        """Checks whether cached predictions already include strength-gate metadata."""
        if not isinstance(predictions, dict) or not predictions:
            return False

        for category, details in predictions.items():
            if not isinstance(details, dict):
                return False
            if category == "system":
                continue
            if "strength_gate" not in details:
                return False
        return True

    def _invalidate_user_runtime_cache(self, user_id: int) -> None:
        """Removes all cached runtime data for one user."""
        self.cache.invalidate_user(
            user_id,
            namespaces=(
                "chart_display",
                "predictions",
                "shadbala",
                "timeline",
                "advanced_data",
                "ui_advanced_data",
                "ui_timeline_forecast",
                "chat_advanced_data",
                "chat_timeline_forecast",
            ),
        )

    def _normalize_timeline_event_type(self, raw_event: str) -> str:
        """Maps event detector labels into stable timeline event types."""
        normalized = str(raw_event or "").strip().lower()
        if "career" in normalized:
            return "career"
        if "marriage" in normalized or "partnership" in normalized:
            return "marriage"
        if "finance" in normalized or "financial" in normalized or "wealth" in normalized or "income" in normalized:
            return "finance"
        return "general"

    def _build_timeline_events(
        self,
        raw_events: Any,
        scored_predictions: Dict[str, Dict[str, Any]],
        *,
        language: str = "en",
    ) -> List[Dict[str, str]]:
        """Converts raw event detector output into widget-friendly event dictionaries."""
        normalized_language = self._normalize_language(language)
        if isinstance(raw_events, list):
            raw_event_list = [str(event).strip() for event in raw_events if str(event).strip()]
        else:
            raw_event_list = [
                event.strip()
                for event in str(raw_events or "").split(",")
                if event.strip()
            ]

        timeline_events: List[Dict[str, str]] = []
        for raw_event in raw_event_list:
            event_type = self._normalize_timeline_event_type(raw_event)
            prediction_info = scored_predictions.get(event_type, {})

            timeline_events.append(
                {
                    "type": event_type,
                    "confidence": prediction_info.get(
                        "confidence",
                        "medium" if event_type != "general" else "low",
                    ),
                    "summary": prediction_info.get("summary", raw_event),
                }
            )

        if not timeline_events:
            timeline_events.append(
                {
                    "type": "general",
                    "confidence": "low",
                    "summary": (
                        "सामान्य जीवन चरण"
                        if normalized_language == "hi"
                        else "ସାଧାରଣ ଜୀବନ ପର୍ଯ୍ୟାୟ"
                        if normalized_language == "or"
                        else "General life phase"
                    ),
                }
            )

        return timeline_events

    def _score_rule_engine_output(
        self,
        raw_predictions: List[str],
        rules: List[Rule],
        *,
        chart_data_models: Optional[List[Any]] = None,
        strength_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Maps raw rule-engine text back to rule metadata before scoring."""
        logger.info("Prediction scoring started with %d matched rule(s).", len(raw_predictions))

        rule_lookup: Dict[str, List[Rule]] = {}
        for rule in rules:
            normalized_text = rule.result_text.strip().lower()
            rule_lookup.setdefault(normalized_text, []).append(rule)

        lagna_sign = self._resolve_lagna_sign(chart_data_models or [])
        functional_roles_map = (
            self.functional_nature_engine.get_planet_roles(lagna_sign)
            if lagna_sign
            else {}
        )

        usage_counter: Dict[str, int] = {}
        scorer_input = []
        for raw_prediction in raw_predictions:
            if isinstance(raw_prediction, dict):
                raw_text = str(
                    raw_prediction.get("text")
                    or raw_prediction.get("result_text")
                    or ""
                ).strip()
            else:
                raw_text = str(raw_prediction).strip()

            normalized_text = raw_text.strip().lower()
            matching_rules = rule_lookup.get(normalized_text, [])
            usage_index = usage_counter.get(normalized_text, 0)
            matched_rule = None
            if matching_rules:
                matched_rule = matching_rules[min(usage_index, len(matching_rules) - 1)]
                usage_counter[normalized_text] = usage_index + 1

            functional_roles = self._build_rule_functional_roles(
                matched_rule,
                functional_roles_map=functional_roles_map,
            )

            scorer_input.append(
                {
                    "text": raw_text,
                    "category": (
                        raw_prediction.get("category")
                        if isinstance(raw_prediction, dict) and raw_prediction.get("category")
                        else matched_rule.category if matched_rule else "general"
                    ),
                    "effect": (
                        raw_prediction.get("effect")
                        if isinstance(raw_prediction, dict) and raw_prediction.get("effect")
                        else matched_rule.effect if matched_rule else "positive"
                    ),
                    "weight": (
                        raw_prediction.get("weight")
                        if isinstance(raw_prediction, dict) and raw_prediction.get("weight") is not None
                        else matched_rule.weight if matched_rule else 1.0
                    ),
                    "result_key": (
                        raw_prediction.get("result_key")
                        if isinstance(raw_prediction, dict) and raw_prediction.get("result_key")
                        else matched_rule.result_key if matched_rule else None
                    ),
                    "rule_confidence": (
                        raw_prediction.get("rule_confidence")
                        if isinstance(raw_prediction, dict) and raw_prediction.get("rule_confidence")
                        else matched_rule.confidence if matched_rule else "medium"
                    ),
                    "trace": (
                        raw_prediction.get("trace")
                        if isinstance(raw_prediction, dict)
                        else []
                    ),
                    "functional_lagna": lagna_sign,
                    "functional_roles": functional_roles,
                }
            )

        def _safe_weight(item: Dict[str, Any]) -> float:
            try:
                return float(item.get("weight", 0.0) or 0.0)
            except (TypeError, ValueError):
                return 0.0

        scorer_input.sort(key=_safe_weight, reverse=True)
        unique_scorer_input: Dict[str, Dict[str, Any]] = {}
        for item in scorer_input:
            dedupe_key = str(item.get("result_key") or item.get("text") or "").strip().lower()
            if not dedupe_key or dedupe_key in unique_scorer_input:
                continue
            unique_scorer_input[dedupe_key] = item
        scorer_input = list(unique_scorer_input.values())

        scored_predictions = score_predictions(
            scorer_input,
            strength_payload=strength_payload,
        )
        scored_predictions = self.interpreter.refine_scored_predictions(scored_predictions)

        for category, details in scored_predictions.items():
            logger.info(
                "Prediction category '%s' scored %.2f with %s confidence and %s effect.",
                category,
                details.get("score", 0.0),
                details.get("confidence", "low"),
                details.get("effect", "neutral"),
            )

        return scored_predictions

    @staticmethod
    def _resolve_lagna_sign(chart_data_models: List[Any]) -> str | None:
        for row in chart_data_models or []:
            raw_planet = (
                row.get("planet_name")
                if isinstance(row, dict)
                else getattr(row, "planet_name", None)
            )
            planet = str(raw_planet or "").strip().lower()
            if planet not in {"ascendant", "lagna"}:
                continue

            raw_sign = row.get("sign") if isinstance(row, dict) else getattr(row, "sign", None)
            sign = str(raw_sign or "").strip().lower()
            if sign:
                return sign
        return None

    @staticmethod
    def _normalize_planet_token(raw_value: Any) -> str:
        token = str(raw_value or "").strip().lower()
        canonical = {
            "sun",
            "moon",
            "mars",
            "mercury",
            "jupiter",
            "venus",
            "saturn",
            "rahu",
            "ketu",
        }
        return token if token in canonical else ""

    def _extract_planets_from_condition(self, condition: Any) -> List[str]:
        if isinstance(condition, list):
            planets: List[str] = []
            for item in condition:
                planets.extend(self._extract_planets_from_condition(item))
            return planets

        if not isinstance(condition, dict):
            return []

        planets: List[str] = []
        for key in ("planet", "from", "to", "from_planet", "to_planet"):
            normalized = self._normalize_planet_token(condition.get(key))
            if normalized:
                planets.append(normalized)

        raw_planet_list = condition.get("planets", [])
        if isinstance(raw_planet_list, (list, tuple, set)):
            for raw_planet in raw_planet_list:
                normalized = self._normalize_planet_token(raw_planet)
                if normalized:
                    planets.append(normalized)

        if "AND" in condition:
            planets.extend(self._extract_planets_from_condition(condition.get("AND")))
        if "OR" in condition:
            planets.extend(self._extract_planets_from_condition(condition.get("OR")))

        deduped: List[str] = []
        for planet in planets:
            if planet not in deduped:
                deduped.append(planet)
        return deduped

    def _build_rule_functional_roles(
        self,
        matched_rule: Optional[Rule],
        *,
        functional_roles_map: Dict[str, str],
    ) -> List[Dict[str, str]]:
        if matched_rule is None or not functional_roles_map:
            return []

        try:
            condition_payload = json.loads(matched_rule.condition_json or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            return []

        planets = self._extract_planets_from_condition(condition_payload)
        if not planets:
            return []

        role_rows: List[Dict[str, str]] = []
        for planet in planets:
            role_rows.append(
                {
                    "planet": planet,
                    "role": str(functional_roles_map.get(planet, "neutral")).strip().lower() or "neutral",
                }
            )
        return role_rows

    def generate_and_save_chart(self, user_data: dict) -> Tuple[List[Dict], Dict[str, Dict[str, Any]]]:
        """
        Parses user data, computes chart, executes rules, and persists everything.
        Returns display data dictionaries and category-scored predictions.
        """
        failure_registry.clear()
        validated_data = self.prepare_user_input(user_data)
        log_user_action("generate_chart", name=validated_data["name"], place=validated_data["place"])

        # Create Domain Model
        user = User(
            name=validated_data["name"],
            dob=validated_data["dob"],
            tob=validated_data["tob"],
            place=validated_data["place"],
            latitude=validated_data["latitude"],
            longitude=validated_data["longitude"],
            state=validated_data.get("state"),
            city=validated_data.get("city"),
        )

        # Execute Engine
        chart_data_models = execute_safely(
            lambda: self._calculate_chart_data(user),
            logger=logger,
            operation_name="Chart calculation",
            user_message="Unable to generate the chart right now. Please verify the birth details and try again.",
            raise_app_error=True,
        )

        # Database Persistence
        # 1. Save User and get ID
        user_id = execute_safely(
            lambda: self.user_repo.save(user),
            logger=logger,
            operation_name="User persistence",
            user_message="Chart generation succeeded, but saving the user failed. Please try again.",
            raise_app_error=True,
        )
        
        # 2. Assign User ID to ChartData objects and bulk save
        for cd in chart_data_models:
            cd.user_id = user_id
        try:
            execute_safely(
                lambda: self.chart_repo.save_bulk(chart_data_models),
                logger=logger,
                operation_name="Chart persistence",
                user_message="Chart generation succeeded, but saving chart data failed. Please try again.",
                raise_app_error=True,
            )
        except AppError:
            execute_safely(
                lambda: self.user_repo.delete(user_id),
                logger=logger,
                operation_name="User rollback after chart persistence failure",
                user_message="Temporary data cleanup failed.",
                fallback=None,
            )
            raise

        shadbala = self._get_or_calculate_shadbala(chart_data_models)

        # Rule Engine Evaluation
        predictions = self._evaluate_chart_predictions(
            chart_data_models,
            shadbala_payload=shadbala,
        )
            
        if not predictions:
            predictions = self._system_prediction("Chart generated successfully. No matching rules found.")
            logger.warning("No rules matched for user '%s'. Returning system fallback prediction.", user.name)

        # Format for UI Response Layer
        display_data = self._format_display_data(chart_data_models)
        self._cache_chart_bundle(user_id, display_data=display_data, predictions=predictions, shadbala=shadbala)
        log_calculation_step("chart_generation_completed", user_id=user_id, rows=len(display_data), prediction_categories=len(predictions))

        return display_data, predictions

    def get_all_users_dicts(self) -> List[Dict]:
        """Fetches all users and formats them for the UI table."""
        users = self.user_repo.get_all()
        return [
            {
                "id": u.id,
                "name": u.name,
                "dob": u.dob,
                "place": u.place,
                "state": u.state,
                "city": u.city,
            } for u in users
        ]

    def get_available_states(self) -> List[str]:
        """Returns all known states from the local location dataset."""
        return self.location_repo.get_states()

    def get_cities_for_state(self, state: str) -> List[str]:
        """Returns cities for a given state from the local location dataset."""
        return self.location_repo.get_cities_by_state(state)

    def get_location_details(self, state: str, city: str) -> Dict[str, Any]:
        """Returns coordinates and metadata for a selected city."""
        location = self.location_repo.get_location(state, city)
        if not location:
            raise ValueError("Selected city could not be found in the location database.")
        return location

    def delete_user(self, user_id: int):
        self.user_repo.delete(user_id)
        self._invalidate_user_runtime_cache(user_id)

    def save_astrology_rule(self, rule_data: dict):
        from app.models.domain import Rule
        log_user_action("save_rule", category=rule_data.get("category", "general"), priority=rule_data.get("priority", 0))
        r = Rule(
            condition_json=rule_data["condition_json"],
            result_text=rule_data["result_text"],
            result_key=rule_data.get("result_key"),
            priority=rule_data.get("priority", 0),
            category=rule_data.get("category", "general"),
            effect=rule_data.get("effect", "positive"),
            weight=rule_data.get("weight", 1.0),
            confidence=rule_data.get("confidence", "medium")
        )
        self.rule_repo.save(r)
        self.cache.clear(
            namespaces=(
                "predictions",
                "timeline",
                "advanced_data",
                "ui_advanced_data",
                "ui_timeline_forecast",
                "chat_advanced_data",
                "chat_timeline_forecast",
            )
        )

    def get_timeline_data(self, user_id: int, *, language: str = "en") -> Dict[str, Any]:
        """
        Builds unified timeline data from dasha periods, detected events, and prediction scores.

        Output shape:
        {
            "timeline": [
                {
                    "planet": "Saturn",
                    "start": "2025-01-01",
                    "end": "2044-01-01",
                    "events": [
                        {"type": "career", "confidence": "high", "summary": "..."}
                    ]
                }
            ],
            "prediction_scores": {...}
        }
        """
        normalized_language = self._normalize_language(language)
        cached_timeline = self.cache.get("timeline", user_id)
        if isinstance(cached_timeline, dict):
            cached_language = str(cached_timeline.get("_language", "en")).strip().lower() or "en"
            if cached_language == normalized_language:
                logger.info("Timeline cache hit for user %s.", user_id)
                return cached_timeline
        elif cached_timeline is not None and normalized_language == "en":
            logger.info("Timeline cache hit for user %s.", user_id)
            return cached_timeline

        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found.")

        chart_data_models = self.chart_repo.get_by_user_id(user_id)
        if not chart_data_models:
            raise ValueError("No chart data found for this user.")

        from app.services.astrology_advanced_service import AstrologyAdvancedService

        advanced_service = AstrologyAdvancedService()
        advanced_data = advanced_service.generate_advanced_data(
            chart_data_models,
            user.dob,
            language=normalized_language,
        )
        scored_predictions = self.cache.get("predictions", user_id)
        if not self._predictions_are_strength_gated(scored_predictions):
            cached_shadbala = self.cache.get("shadbala", user_id)
            normalized_shadbala = self._get_or_calculate_shadbala(
                chart_data_models,
                precomputed=cached_shadbala if isinstance(cached_shadbala, dict) else None,
            )
            scored_predictions = self._evaluate_chart_predictions(
                chart_data_models,
                shadbala_payload=normalized_shadbala,
            )
            if scored_predictions:
                self.cache.set("predictions", user_id, scored_predictions)
                self.cache.set("shadbala", user_id, normalized_shadbala)

        timeline_rows = []
        for dasha in advanced_data.get("dasha", []):
            timeline_rows.append(
                {
                    "planet": dasha.get("planet", "Unknown"),
                    "start": dasha.get("start", ""),
                    "end": dasha.get("end", ""),
                    "events": self._build_timeline_events(
                        dasha.get("events", ""),
                        scored_predictions,
                        language=normalized_language,
                    ),
                }
            )

        logger.info(
            "Built life timeline for user %s with %d dasha period(s).",
            user_id,
            len(timeline_rows),
        )

        timeline_payload = {
            "timeline": timeline_rows,
            "prediction_scores": scored_predictions,
            "_language": normalized_language,
        }
        self.cache.set("timeline", user_id, timeline_payload)
        return timeline_payload

    @staticmethod
    def _normalize_language(language: str) -> str:
        normalized = str(language or "en").strip().lower() or "en"
        if normalized not in {"en", "hi", "or"}:
            return "en"
        return normalized

    def load_chart_for_user(self, user_id: int) -> Tuple[List[Dict], Dict[str, Dict[str, Any]]]:
        """Loads a previously calculated chart for a user and re-evaluates rules."""
        failure_registry.clear()
        cached_display = self.cache.get("chart_display", user_id)
        cached_predictions = self.cache.get("predictions", user_id)
        raw_cached_shadbala = self.cache.get("shadbala", user_id)
        cached_shadbala = (
            normalize_shadbala_payload(raw_cached_shadbala)
            if raw_cached_shadbala is not None
            else None
        )
        predictions_cached_with_gate = self._predictions_are_strength_gated(cached_predictions)
        
        if (
            cached_display is not None
            and cached_predictions is not None
            and cached_shadbala is not None
            and predictions_cached_with_gate
        ):
            logger.info("Chart cache hit for user %s.", user_id)
            return cached_display, cached_predictions

        chart_data_models = self.chart_repo.get_by_user_id(user_id)
        if not chart_data_models:
            raise ValueError("No chart data found for this user.")

        shadbala = self._get_or_calculate_shadbala(
            chart_data_models,
            precomputed=cached_shadbala,
        )
        predictions = (
            cached_predictions
            if cached_predictions is not None and predictions_cached_with_gate
            else self._evaluate_chart_predictions(
                chart_data_models,
                shadbala_payload=shadbala,
            )
        )
            
        if not predictions:
            predictions = self._system_prediction("Chart generated successfully. No matching rules found.")

        display_data = cached_display if cached_display is not None else self._format_display_data(chart_data_models)
        self._cache_chart_bundle(user_id, display_data=display_data, predictions=predictions, shadbala=shadbala)
        return display_data, predictions
