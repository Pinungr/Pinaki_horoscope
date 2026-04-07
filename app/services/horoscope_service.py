import logging
from typing import Tuple, List, Dict, Any
from app.repositories.database_manager import DatabaseManager
from app.repositories.user_repo import UserRepository
from app.repositories.chart_repo import ChartRepository
from app.repositories.rule_repo import RuleRepository
from app.engine.calculator import AstrologyEngine
from app.engine.prediction_scorer import score_predictions
from app.engine.rule_engine import RuleEngine
from app.models.domain import User, Rule

logger = logging.getLogger(__name__)

class HoroscopeService:
    """Orchestrates astrology logic and database persistence."""
    def __init__(self, db_manager: DatabaseManager):
        self.user_repo = UserRepository(db_manager)
        self.chart_repo = ChartRepository(db_manager)
        self.rule_repo = RuleRepository(db_manager)

    def _evaluate_chart_predictions(self, chart_data_models: List[Any]) -> Dict[str, Dict[str, Any]]:
        """Evaluates rules for an existing chart and returns scored predictions."""
        rules = self.rule_repo.get_all()
        if not rules:
            return {}

        rule_engine = RuleEngine(rules)
        raw_predictions = rule_engine.evaluate(chart_data_models)
        if not raw_predictions:
            return {}

        return self._score_rule_engine_output(raw_predictions, rules)

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
        for raw_text in raw_predictions:
            normalized_text = raw_text.strip().lower()
            matching_rules = rule_lookup.get(normalized_text, [])
            usage_index = usage_counter.get(normalized_text, 0)
            matched_rule = None
            if matching_rules:
                matched_rule = matching_rules[min(usage_index, len(matching_rules) - 1)]
                usage_counter[normalized_text] = usage_index + 1

            scorer_input.append({
                "text": raw_text,
                "category": matched_rule.category if matched_rule else "general",
                "weight": matched_rule.weight if matched_rule else 1.0,
                "rule_confidence": matched_rule.confidence if matched_rule else "medium",
            })

        scored_predictions = score_predictions(scorer_input)

        for category, details in scored_predictions.items():
            logger.info(
                "Prediction category '%s' scored %.2f with %s confidence.",
                category,
                details.get("score", 0.0),
                details.get("confidence", "low"),
            )

        return scored_predictions

    def generate_and_save_chart(self, user_data: dict) -> Tuple[List[Dict], Dict[str, Dict[str, Any]]]:
        """
        Parses user data, computes chart, executes rules, and persists everything.
        Returns display data dictionaries and category-scored predictions.
        """
        try:
            lat = float(user_data.get("latitude", 0.0))
            lon = float(user_data.get("longitude", 0.0))
        except ValueError:
            raise ValueError("Latitude and Longitude must be valid numbers.")

        # Create Domain Model
        user = User(
            name=user_data["name"],
            dob=user_data["dob"],
            tob=user_data["tob"],
            place=user_data["place"],
            latitude=lat,
            longitude=lon
        )

        # Execute Engine
        astrology_engine = AstrologyEngine()
        chart_data_models = astrology_engine.calculate_chart(user)

        # Database Persistence
        # 1. Save User and get ID
        user_id = self.user_repo.save(user)
        
        # 2. Assign User ID to ChartData objects and bulk save
        for cd in chart_data_models:
            cd.user_id = user_id
        self.chart_repo.save_bulk(chart_data_models)

        # Rule Engine Evaluation
        predictions = self._evaluate_chart_predictions(chart_data_models)
            
        if not predictions:
            predictions = {
                "system": {
                    "score": 0.0,
                    "confidence": "low",
                    "summary": "Chart generated successfully. No matching rules found.",
                }
            }

        # Format for UI Response Layer
        display_data = [
            {
                "Planet": cd.planet_name,
                "Sign": cd.sign,
                "House": cd.house,
                "Degree": round(cd.degree, 2)
            }
            for cd in chart_data_models
        ]

        return display_data, predictions

    def get_all_users_dicts(self) -> List[Dict]:
        """Fetches all users and formats them for the UI table."""
        users = self.user_repo.get_all()
        return [
            {
                "id": u.id,
                "name": u.name,
                "dob": u.dob,
                "place": u.place
            } for u in users
        ]

    def delete_user(self, user_id: int):
        self.user_repo.delete(user_id)

    def save_astrology_rule(self, rule_data: dict):
        from app.models.domain import Rule
        r = Rule(
            condition_json=rule_data["condition_json"],
            result_text=rule_data["result_text"],
            priority=rule_data.get("priority", 0),
            category=rule_data.get("category", "general"),
            weight=rule_data.get("weight", 1.0),
            confidence=rule_data.get("confidence", "medium")
        )
        self.rule_repo.save(r)

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
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found.")

        chart_data_models = self.chart_repo.get_by_user_id(user_id)
        if not chart_data_models:
            raise ValueError("No chart data found for this user.")

        from app.services.astrology_advanced_service import AstrologyAdvancedService

        advanced_service = AstrologyAdvancedService()
        advanced_data = advanced_service.generate_advanced_data(chart_data_models, user.dob)
        scored_predictions = self._evaluate_chart_predictions(chart_data_models)

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

        return {
            "timeline": timeline_rows,
            "prediction_scores": scored_predictions,
        }

    def load_chart_for_user(self, user_id: int) -> Tuple[List[Dict], Dict[str, Dict[str, Any]]]:
        """Loads a previously calculated chart for a user and re-evaluates rules."""
        chart_data_models = self.chart_repo.get_by_user_id(user_id)
        if not chart_data_models:
            raise ValueError("No chart data found for this user.")

        predictions = self._evaluate_chart_predictions(chart_data_models)
            
        if not predictions:
            predictions = {
                "system": {
                    "score": 0.0,
                    "confidence": "low",
                    "summary": "Chart generated successfully. No matching rules found.",
                }
            }

        display_data = [
            {
                "Planet": cd.planet_name,
                "Sign": cd.sign,
                "House": cd.house,
                "Degree": round(cd.degree, 2)
            }
            for cd in chart_data_models
        ]
        return display_data, predictions
