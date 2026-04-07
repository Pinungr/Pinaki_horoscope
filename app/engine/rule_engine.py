import json
from typing import List, Dict, Any
from app.models.domain import Rule, ChartData

class RuleEngine:
    def __init__(self, rules: List[Rule]):
        self.rules = sorted(rules, key=lambda r: r.priority, reverse=True)

    def evaluate(self, chart_data: List[ChartData]) -> List[str]:
        """Evaluates all rules against the provided chart data."""
        predictions = []
        for rule in self.rules:
            try:
                condition = json.loads(rule.condition_json)
                if self._evaluate_condition(condition, chart_data):
                    predictions.append(rule.result_text)
            except json.JSONDecodeError:
                # Log error in real app
                continue
        return predictions

    def _evaluate_condition(self, condition: Any, chart_data: List[ChartData]) -> bool:
        if not isinstance(condition, dict):
            return False

        if "AND" in condition:
            return all(self._evaluate_condition(c, chart_data) for c in condition["AND"])
        
        if "OR" in condition:
            return any(self._evaluate_condition(c, chart_data) for c in condition["OR"])

        # Simple condition matching
        return self._match_simple_condition(condition, chart_data)

    def _match_simple_condition(self, condition: Dict[str, Any], chart_data: List[ChartData]) -> bool:
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
