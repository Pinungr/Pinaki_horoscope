import json
import logging
from typing import List, Dict, Any, Optional
from app.models.domain import Rule, ChartData
from app.engine.chart_data_access import (
    extract_house,
    extract_planet_name,
    get_planet_data,
    get_planet_house,
    normalize_planet_name,
)
from app.utils.logger import log_rule_match
from core.engines.aspect_engine import calculate_aspects


logger = logging.getLogger(__name__)

HOUSE_GROUPS = {
    "kendra": {1, 4, 7, 10},
    "trikona": {1, 5, 9},
    "dusthana": {6, 8, 12},
}

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
                trace: List[str] = []
                if self._evaluate_condition(condition, chart_data, computed_aspects, trace=trace):
                    predictions.append(
                        {
                            "rule": str(rule.result_key or f"rule_{rule.id or rule.result_text}"),
                            "text": rule.result_text,
                            "result_text": rule.result_text,
                            "result_key": rule.result_key,
                            "category": rule.category,
                            "effect": rule.effect,
                            "weight": rule.weight,
                            "rule_confidence": rule.confidence,
                            "rule_id": rule.id,
                            "priority": rule.priority,
                            "trace": trace,
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
        predictions = self._deduplicate_predictions(predictions)
        logger.info("Rule evaluation completed with %d match(es).", len(predictions))
        return predictions

    def _evaluate_condition(
        self,
        condition: Any,
        chart_data: List[ChartData],
        aspects: Optional[List[Dict[str, Any]]] = None,
        *,
        trace: Optional[List[str]] = None,
    ) -> bool:
        if not isinstance(condition, dict):
            if trace is not None:
                trace.append("Invalid condition payload.")
            return False

        if "AND" in condition:
            and_conditions = condition["AND"]
            if not isinstance(and_conditions, list):
                if trace is not None:
                    trace.append("Invalid AND condition list.")
                return False

            all_matched = True
            for index, child_condition in enumerate(and_conditions):
                child_trace: List[str] = []
                child_matched = self._evaluate_condition(
                    child_condition,
                    chart_data,
                    aspects,
                    trace=child_trace,
                )
                if trace is not None:
                    trace.extend(child_trace)
                    trace.append(f"AND[{index}] => {'matched' if child_matched else 'failed'}")
                if not child_matched:
                    all_matched = False
            return all_matched
        
        if "OR" in condition:
            or_conditions = condition["OR"]
            if not isinstance(or_conditions, list):
                if trace is not None:
                    trace.append("Invalid OR condition list.")
                return False

            any_matched = False
            for index, child_condition in enumerate(or_conditions):
                child_trace: List[str] = []
                child_matched = self._evaluate_condition(
                    child_condition,
                    chart_data,
                    aspects,
                    trace=child_trace,
                )
                if trace is not None:
                    trace.extend(child_trace)
                    trace.append(f"OR[{index}] => {'matched' if child_matched else 'failed'}")
                if child_matched:
                    any_matched = True
            return any_matched

        # Simple condition matching
        return self._match_simple_condition(condition, chart_data, aspects, trace=trace)

    def _match_simple_condition(
        self,
        condition: Dict[str, Any],
        chart_data: List[ChartData],
        aspects: Optional[List[Dict[str, Any]]] = None,
        *,
        trace: Optional[List[str]] = None,
    ) -> bool:
        if condition.get("type") == "conjunction":
            return self._match_conjunction_condition(condition, chart_data, trace=trace)

        if condition.get("type") == "aspect":
            matched = self._match_aspect_condition(
                condition,
                aspects if aspects is not None else calculate_aspects(chart_data),
            )
            if trace is not None:
                from_planet = self._normalize_planet_name(condition.get("from"))
                to_planet = self._normalize_planet_name(condition.get("to"))
                trace.append(
                    f"Aspect check: {from_planet or '*'} -> {to_planet or '*'} => {'matched' if matched else 'not matched'}"
                )
            return matched

        if condition.get("type") == "in_kendra":
            return self._match_house_group_condition(condition, chart_data, "kendra", trace=trace)

        if condition.get("type") == "relative_house":
            return self._match_relative_house_condition(condition, chart_data, trace=trace)

        if self._is_aspect_condition(condition):
            matched = self._match_aspect_condition(
                condition,
                aspects if aspects is not None else calculate_aspects(chart_data),
            )
            if trace is not None:
                trace.append(f"Aspect condition => {'matched' if matched else 'not matched'}")
            return matched

        target_planet = condition.get("planet")
        target_sign = condition.get("sign")
        target_house = condition.get("house")

        # Find matching planets in chart data
        for cd in chart_data:
            current_planet = self._extract_planet_name(cd)
            current_sign = getattr(cd, "sign", None) if not isinstance(cd, dict) else cd.get("sign", cd.get("Sign"))
            current_house = self._extract_house(cd)

            if target_planet and current_planet != self._normalize_planet_name(target_planet):
                continue
            if target_sign and str(current_sign) != str(target_sign):
                continue
            if target_house and current_house != target_house:
                continue
             
            # If we reach here, it means all specified criteria matched this ChartData
        # For a simple condition, we only need ONE matching entity in the chart.
            if trace is not None:
                trace.append(
                    f"Simple condition matched: planet={current_planet or '*'} sign={current_sign or '*'} house={current_house}"
                )
            return True
             
        if trace is not None:
            trace.append("Simple condition did not match.")
        return False

    @staticmethod
    def _match_conjunction_condition(
        condition: Dict[str, Any],
        chart_data: List[Any],
        *,
        trace: Optional[List[str]] = None,
    ) -> bool:
        target_planets = condition.get("planets", [])
        if not isinstance(target_planets, list):
            if trace is not None:
                trace.append("Conjunction condition has invalid planets payload.")
            return False

        normalized_targets = []
        for planet in target_planets:
            planet_name = RuleEngine._normalize_planet_name(planet)
            if planet_name and planet_name not in normalized_targets:
                normalized_targets.append(planet_name)

        if len(normalized_targets) < 2:
            if trace is not None:
                trace.append("Conjunction requires at least two planets.")
            return False

        target_houses: List[int] = []
        house_pairs: List[str] = []
        for planet_name in normalized_targets:
            house = RuleEngine.get_planet_house(chart_data, planet_name)
            if house is None:
                if trace is not None:
                    trace.append(f"Conjunction failed: missing/invalid house for {planet_name}.")
                return False
            target_houses.append(house)
            house_pairs.append(f"{planet_name}={house}")

        matched = len(set(target_houses)) == 1
        if trace is not None:
            trace.append(
                f"Conjunction houses ({', '.join(house_pairs)}) => {'matched' if matched else 'not matched'}"
            )
        return matched

    @staticmethod
    def get_planet_house(chart_data: List[Any], planet_name: str) -> Optional[int]:
        return get_planet_house(chart_data, planet_name)

    @staticmethod
    def get_planet_data(chart_data: List[Any], planet_name: str) -> Optional[Dict[str, Any]]:
        return get_planet_data(chart_data, planet_name)

    @staticmethod
    def _match_house_group_condition(
        condition: Dict[str, Any],
        chart_data: List[Any],
        group_name: str,
        *,
        trace: Optional[List[str]] = None,
    ) -> bool:
        target_planet = condition.get("planet")
        target_house = RuleEngine.get_planet_house(chart_data, target_planet)
        if target_house is None:
            if trace is not None:
                trace.append(f"{group_name} check failed: missing house for {target_planet}.")
            return False

        matched = target_house in HOUSE_GROUPS.get(group_name, set())
        if trace is not None:
            trace.append(
                f"{RuleEngine._normalize_planet_name(target_planet)} house={target_house} in {group_name} => "
                f"{'matched' if matched else 'not matched'}"
            )
        return matched

    @staticmethod
    def _match_relative_house_condition(
        condition: Dict[str, Any],
        chart_data: List[Any],
        *,
        trace: Optional[List[str]] = None,
    ) -> bool:
        from_planet = condition.get("from")
        to_planet = condition.get("to")
        target_houses = condition.get("houses", [])

        if not isinstance(target_houses, list) or not target_houses:
            if trace is not None:
                trace.append("relative_house requires a non-empty houses list.")
            return False

        normalized_target_houses = set()
        for house in target_houses:
            try:
                house_number = int(house)
            except (TypeError, ValueError):
                continue
            if 1 <= house_number <= 12:
                normalized_target_houses.add(house_number)

        if not normalized_target_houses:
            if trace is not None:
                trace.append("relative_house has no valid target houses.")
            return False

        from_house = RuleEngine.get_planet_house(chart_data, from_planet)
        to_house = RuleEngine.get_planet_house(chart_data, to_planet)
        if from_house is None or to_house is None:
            if trace is not None:
                trace.append("relative_house failed: missing house for source/target planet.")
            return False

        relative_house = (to_house - from_house) % 12 + 1
        matched = relative_house in normalized_target_houses
        if trace is not None:
            normalized_from = RuleEngine._normalize_planet_name(from_planet) or "unknown"
            normalized_to = RuleEngine._normalize_planet_name(to_planet) or "unknown"
            trace.append(f"{normalized_from}-{normalized_to} relative house = {relative_house}")
            trace.append(
                f"Condition satisfied: relative house in {sorted(normalized_target_houses)} => "
                f"{'matched' if matched else 'not matched'}"
            )
        return matched

    @staticmethod
    def _deduplicate_predictions(predictions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        unique_predictions: Dict[str, Dict[str, Any]] = {}

        for prediction in predictions:
            dedupe_key = str(
                prediction.get("rule")
                or prediction.get("result_key")
                or prediction.get("rule_id")
                or prediction.get("text")
                or ""
            ).strip().lower()
            if not dedupe_key:
                continue

            current_weight = RuleEngine._safe_weight(prediction.get("weight", 0.0))
            existing = unique_predictions.get(dedupe_key)
            if existing is None:
                unique_predictions[dedupe_key] = prediction
                continue

            existing_weight = RuleEngine._safe_weight(existing.get("weight", 0.0))
            if current_weight > existing_weight:
                unique_predictions[dedupe_key] = prediction

        return list(unique_predictions.values())

    @staticmethod
    def _safe_weight(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _normalize_planet_name(planet_name: Any) -> str:
        return normalize_planet_name(planet_name)

    @staticmethod
    def _extract_planet_name(item: Any) -> str:
        return extract_planet_name(item)

    @staticmethod
    def _extract_house(item: Any) -> Optional[int]:
        return extract_house(item)

    @staticmethod
    def _is_aspect_condition(condition: Dict[str, Any]) -> bool:
        if condition.get("type") == "aspect":
            return True
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
        if not isinstance(aspects, list) or not aspects:
            return False

        target_from_planet = RuleEngine._normalize_planet_name(condition.get("from_planet", condition.get("from")))
        target_to_planet = RuleEngine._normalize_planet_name(condition.get("to_planet", condition.get("to")))
        target_from_house = condition.get("from_house")
        target_to_house = condition.get("to_house")
        target_aspect_type = condition.get("aspect_type", "drishti" if condition.get("type") == "aspect" else None)

        for aspect in aspects:
            aspect_from = RuleEngine._normalize_planet_name(aspect.get("from_planet"))
            aspect_to = RuleEngine._normalize_planet_name(aspect.get("to_planet"))

            if target_from_planet and aspect_from != target_from_planet:
                continue
            if target_to_planet and aspect_to != target_to_planet:
                continue
            if target_from_house and aspect.get("from_house") != target_from_house:
                continue
            if target_to_house and aspect.get("to_house") != target_to_house:
                continue
            if target_aspect_type and aspect.get("aspect_type") != target_aspect_type:
                continue
            return True

        return False
