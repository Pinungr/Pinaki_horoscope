import logging
from typing import Tuple, List, Dict, Any, Optional
from app.repositories.database_manager import DatabaseManager
from app.repositories.user_repo import UserRepository
from app.repositories.chart_repo import ChartRepository
from app.repositories.location_repo import LocationRepository
from app.repositories.rule_repo import RuleRepository
from app.engine.calculator import AstrologyEngine
from app.engine.prediction_scorer import score_predictions
from app.engine.rule_engine import RuleEngine
from app.engine.interpreter import InterpreterEngine
from app.models.domain import User, Rule
from app.utils.cache import get_astrology_cache
from app.utils.logger import log_user_action, log_calculation_step
from app.utils.validators import validate_user_input
from app.utils.safe_execution import AppError, execute_safely

logger = logging.getLogger(__name__)

class HoroscopeService:
    """Orchestrates astrology logic and database persistence."""
    def __init__(self, db_manager: DatabaseManager):
        self.user_repo = UserRepository(db_manager)
        self.chart_repo = ChartRepository(db_manager)
        self.rule_repo = RuleRepository(db_manager)
        self.location_repo = LocationRepository(db_manager)
        self.interpreter = InterpreterEngine()
        self.cache = get_astrology_cache()

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
    def _system_prediction(summary: str) -> Dict[str, Dict[str, Any]]:
        """Builds a stable fallback prediction payload for UI consumers."""
        return {
            "system": {
                "score": 0.0,
                "confidence": "low",
                "summary": summary,
            }
        }

    def _evaluate_chart_predictions(self, chart_data_models: List[Any]) -> Dict[str, Dict[str, Any]]:
        """Evaluates rules for an existing chart and returns scored predictions."""
        rules = execute_safely(
            lambda: self.rule_repo.get_all(),
            logger=logger,
            operation_name="Rule repository fetch",
            user_message="Predictions are unavailable right now.",
            fallback=[],
        )
        if not rules:
            return {}

        rule_engine = RuleEngine(rules)
        raw_predictions = execute_safely(
            lambda: rule_engine.evaluate(chart_data_models),
            logger=logger,
            operation_name="Rule engine evaluation",
            user_message="Predictions are unavailable right now.",
            fallback=[],
        )
        if not raw_predictions:
            return {}

        return execute_safely(
            lambda: self._score_rule_engine_output(raw_predictions, rules),
            logger=logger,
            operation_name="Prediction scoring",
            user_message="Predictions are unavailable right now.",
            fallback={},
        )

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
    ) -> None:
        """Stores chart and prediction results for one user when available."""
        if display_data is not None:
            self.cache.set("chart_display", user_id, display_data)
        if predictions is not None:
            self.cache.set("predictions", user_id, predictions)

    def _invalidate_user_runtime_cache(self, user_id: int) -> None:
        """Removes all cached runtime data for one user."""
        self.cache.invalidate_user(
            user_id,
            namespaces=("chart_display", "predictions", "advanced_data", "timeline"),
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
    ) -> List[Dict[str, str]]:
        """Converts raw event detector output into widget-friendly event dictionaries."""
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
                    "summary": "General life phase",
                }
            )

        return timeline_events

    def _score_rule_engine_output(self, raw_predictions: List[str], rules: List[Rule]) -> Dict[str, Dict[str, Any]]:
        """Maps raw rule-engine text back to rule metadata before scoring."""
        logger.info("Prediction scoring started with %d matched rule(s).", len(raw_predictions))

        rule_lookup: Dict[str, List[Rule]] = {}
        for rule in rules:
            normalized_text = rule.result_text.strip().lower()
            rule_lookup.setdefault(normalized_text, []).append(rule)

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
                    "rule_confidence": (
                        raw_prediction.get("rule_confidence")
                        if isinstance(raw_prediction, dict) and raw_prediction.get("rule_confidence")
                        else matched_rule.confidence if matched_rule else "medium"
                    ),
                }
            )

        scored_predictions = score_predictions(scorer_input)
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

    def generate_and_save_chart(self, user_data: dict) -> Tuple[List[Dict], Dict[str, Dict[str, Any]]]:
        """
        Parses user data, computes chart, executes rules, and persists everything.
        Returns display data dictionaries and category-scored predictions.
        """
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
        astrology_engine = AstrologyEngine()
        chart_data_models = execute_safely(
            lambda: astrology_engine.calculate_chart(user),
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

        # Rule Engine Evaluation
        predictions = self._evaluate_chart_predictions(chart_data_models)
            
        if not predictions:
            predictions = self._system_prediction("Chart generated successfully. No matching rules found.")
            logger.warning("No rules matched for user '%s'. Returning system fallback prediction.", user.name)

        # Format for UI Response Layer
        display_data = self._format_display_data(chart_data_models)
        self._cache_chart_bundle(user_id, display_data=display_data, predictions=predictions)
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
            priority=rule_data.get("priority", 0),
            category=rule_data.get("category", "general"),
            effect=rule_data.get("effect", "positive"),
            weight=rule_data.get("weight", 1.0),
            confidence=rule_data.get("confidence", "medium")
        )
        self.rule_repo.save(r)
        self.cache.clear(namespaces=("predictions", "timeline"))

    def get_timeline_data(self, user_id: int) -> Dict[str, Any]:
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
        cached_timeline = self.cache.get("timeline", user_id)
        if cached_timeline is not None:
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
        advanced_data = advanced_service.generate_advanced_data(chart_data_models, user.dob)
        scored_predictions = self.cache.get("predictions", user_id)
        if scored_predictions is None:
            scored_predictions = self._evaluate_chart_predictions(chart_data_models)
            if scored_predictions:
                self.cache.set("predictions", user_id, scored_predictions)

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
        }
        self.cache.set("timeline", user_id, timeline_payload)
        return timeline_payload

    def load_chart_for_user(self, user_id: int) -> Tuple[List[Dict], Dict[str, Dict[str, Any]]]:
        """Loads a previously calculated chart for a user and re-evaluates rules."""
        cached_display = self.cache.get("chart_display", user_id)
        cached_predictions = self.cache.get("predictions", user_id)
        if cached_display is not None and cached_predictions is not None:
            logger.info("Chart cache hit for user %s.", user_id)
            return cached_display, cached_predictions

        chart_data_models = self.chart_repo.get_by_user_id(user_id)
        if not chart_data_models:
            raise ValueError("No chart data found for this user.")

        predictions = cached_predictions if cached_predictions is not None else self._evaluate_chart_predictions(chart_data_models)
            
        if not predictions:
            predictions = self._system_prediction("Chart generated successfully. No matching rules found.")

        display_data = cached_display if cached_display is not None else self._format_display_data(chart_data_models)
        self._cache_chart_bundle(user_id, display_data=display_data, predictions=predictions)
        return display_data, predictions
