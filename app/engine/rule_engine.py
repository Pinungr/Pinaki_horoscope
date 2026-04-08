import json
import logging
from typing import List, Dict, Any, Optional
from app.models.domain import Rule, ChartData
from app.utils.logger import log_rule_match
from core.engines.aspect_engine import calculate_aspects


logger = logging.getLogger(__name__)

class RuleEngine:
    def __init__(self, rules: List[Rule]):
        self.rules = sorted(rules, key=lambda r: r.priority, reverse=True)

    def evaluate(
        self,
        chart_data: List[ChartData],
        aspects: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """Evaluates all rules against the provided chart data."""
        logger.info("Starting rule evaluation for %d rule(s) against %d chart row(s).", len(self.rules), len(chart_data))
        predictions: List[Dict[str, Any]] = []
        computed_aspects = aspects
        for rule in self.rules:
            try:
                condition = json.loads(rule.condition_json)
                if computed_aspects is None and self._condition_requires_aspects(condition):
                    computed_aspects = calculate_aspects(chart_data)
                if self._evaluate_condition(condition, chart_data, computed_aspects):
                    predictions.append(
                        {
                            "text": rule.result_text,
                            "result_text": rule.result_text,
                            "result_key": rule.result_key,
                            "category": rule.category,
                            "effect": rule.effect,
                            "weight": rule.weight,
                            "rule_confidence": rule.confidence,
                            "rule_id": rule.id,
                            "priority": rule.priority,
                        }
                    )
                    log_rule_match(
                        rule_id=rule.id,
                        result_text=rule.result_text,
                        category=rule.category,
                        priority=rule.priority,
                        effect=rule.effect,
                        weight=rule.weight,
                    )
            except json.JSONDecodeError:
                logger.warning("Skipping invalid rule JSON for rule_id=%s.", rule.id)
                continue
        logger.info("Rule evaluation completed with %d match(es).", len(predictions))
        return predictions

    def _evaluate_condition(
        self,
        condition: Any,
        chart_data: List[ChartData],
        aspects: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        if not isinstance(condition, dict):
            return False

        if "AND" in condition:
            return all(self._evaluate_condition(c, chart_data, aspects) for c in condition["AND"])
        
        if "OR" in condition:
            return any(self._evaluate_condition(c, chart_data, aspects) for c in condition["OR"])

        # Simple condition matching
        return self._match_simple_condition(condition, chart_data, aspects)

    def _match_simple_condition(
        self,
        condition: Dict[str, Any],
        chart_data: List[ChartData],
        aspects: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        if self._is_aspect_condition(condition):
            return self._match_aspect_condition(
                condition,
                aspects if aspects is not None else calculate_aspects(chart_data),
            )

        target_planet = condition.get("planet")
        target_sign = condition.get("sign")
        target_house = condition.get("house")

        # Find matching planets in chart data
        for cd in chart_data:
            if target_planet and cd.planet_name != target_planet:
                continue
            if target_sign and cd.sign != target_sign:
                continue
            if target_house and cd.house != target_house:
                continue
            
            # If we reach here, it means all specified criteria matched this ChartData
            # For a simple condition, we only need ONE matching entity in the chart.
            return True
            
        return False

    @staticmethod
    def _is_aspect_condition(condition: Dict[str, Any]) -> bool:
        aspect_keys = {"from_planet", "to_planet", "from_house", "to_house", "aspect_type"}
        return any(key in condition for key in aspect_keys)

    def _condition_requires_aspects(self, condition: Any) -> bool:
        if not isinstance(condition, dict):
            return False
        if "AND" in condition:
            return any(self._condition_requires_aspects(item) for item in condition["AND"])
        if "OR" in condition:
            return any(self._condition_requires_aspects(item) for item in condition["OR"])
        return self._is_aspect_condition(condition)

    @staticmethod
    def _match_aspect_condition(
        condition: Dict[str, Any],
        aspects: List[Dict[str, Any]],
    ) -> bool:
        target_from_planet = condition.get("from_planet")
        target_to_planet = condition.get("to_planet")
        target_from_house = condition.get("from_house")
        target_to_house = condition.get("to_house")
        target_aspect_type = condition.get("aspect_type")

        for aspect in aspects:
            if target_from_planet and aspect.get("from_planet") != target_from_planet:
                continue
            if target_to_planet and aspect.get("to_planet") != target_to_planet:
                continue
            if target_from_house and aspect.get("from_house") != target_from_house:
                continue
            if target_to_house and aspect.get("to_house") != target_to_house:
                continue
            if target_aspect_type and aspect.get("aspect_type") != target_aspect_type:
                continue
            return True

        return False
