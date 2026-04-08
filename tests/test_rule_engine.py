from __future__ import annotations

import unittest

from app.engine.rule_engine import RuleEngine
from app.models.domain import ChartData, Rule


class RuleEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.chart = [
            ChartData(user_id=1, planet_name="Moon", sign="Cancer", house=10, degree=12.5),
            ChartData(user_id=1, planet_name="Venus", sign="Libra", house=7, degree=18.0),
            ChartData(user_id=1, planet_name="Jupiter", sign="Taurus", house=2, degree=5.0),
        ]

    def test_evaluate_returns_enriched_matches_in_priority_order(self) -> None:
        rules = [
            Rule(
                id=101,
                condition_json='{"planet": "Moon", "house": 10}',
                result_text="Career growth is strongly indicated.",
                result_key="career_growth_strong",
                category="career",
                priority=1,
                weight=1.4,
                confidence="high",
            ),
            Rule(
                id=102,
                condition_json='{"planet": "Moon", "house": 10}',
                result_text="Promotion timing may feel delayed.",
                category="career",
                effect="negative",
                priority=5,
                weight=0.6,
                confidence="medium",
            ),
        ]

        predictions = RuleEngine(rules).evaluate(self.chart)

        self.assertEqual(2, len(predictions))
        self.assertEqual("Promotion timing may feel delayed.", predictions[0]["text"])
        self.assertEqual("negative", predictions[0]["effect"])
        self.assertEqual(0.6, predictions[0]["weight"])
        self.assertEqual("career_growth_strong", predictions[1]["result_key"])
        self.assertEqual("high", predictions[1]["rule_confidence"])

    def test_evaluate_supports_nested_and_or_conditions(self) -> None:
        rules = [
            Rule(
                condition_json='{"AND": [{"planet": "Moon", "house": 10}, {"OR": [{"planet": "Venus", "house": 7}, {"planet": "Mars", "house": 7}]}]}',
                result_text="Career and relationship alignment is present.",
                category="general",
            )
        ]

        predictions = RuleEngine(rules).evaluate(self.chart)

        self.assertEqual(1, len(predictions))
        self.assertEqual("general", predictions[0]["category"])

    def test_evaluate_skips_invalid_rule_json(self) -> None:
        rules = [
            Rule(
                condition_json="{invalid-json}",
                result_text="This should never be returned.",
                category="general",
            )
        ]

        predictions = RuleEngine(rules).evaluate(self.chart)

        self.assertEqual([], predictions)


if __name__ == "__main__":
    unittest.main()
