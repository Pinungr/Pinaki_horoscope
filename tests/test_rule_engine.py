from __future__ import annotations

import unittest
from unittest.mock import patch

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

    def test_evaluate_supports_aspect_conditions(self) -> None:
        chart = [
            ChartData(user_id=1, planet_name="Saturn", sign="Gemini", house=3, degree=10.0),
            ChartData(user_id=1, planet_name="Moon", sign="Leo", house=5, degree=12.0),
        ]
        rules = [
            Rule(
                condition_json='{"from_planet": "Saturn", "to_planet": "Moon", "aspect_type": "drishti"}',
                result_text="Saturn aspects Moon.",
                category="general",
            )
        ]

        predictions = RuleEngine(rules).evaluate(chart)

        self.assertEqual(1, len(predictions))
        self.assertEqual("Saturn aspects Moon.", predictions[0]["text"])

    def test_evaluate_supports_typed_aspect_conditions(self) -> None:
        chart = [
            ChartData(user_id=1, planet_name="Saturn", sign="Gemini", house=3, degree=10.0),
            ChartData(user_id=1, planet_name="Moon", sign="Leo", house=5, degree=12.0),
        ]
        rules = [
            Rule(
                condition_json='{"type": "aspect", "from": "Saturn", "to": "Moon"}',
                result_text="Typed aspect match succeeded.",
                category="general",
            )
        ]

        predictions = RuleEngine(rules).evaluate(chart)

        self.assertEqual(1, len(predictions))
        self.assertEqual("Typed aspect match succeeded.", predictions[0]["text"])

    def test_evaluate_supports_case_insensitive_typed_aspect_conditions(self) -> None:
        chart = [
            ChartData(user_id=1, planet_name="Saturn", sign="Gemini", house=3, degree=10.0),
            ChartData(user_id=1, planet_name="Moon", sign="Leo", house=5, degree=12.0),
        ]
        rules = [
            Rule(
                condition_json='{"type": "aspect", "from": "saturn", "to": "MOON"}',
                result_text="Case-insensitive typed aspect match succeeded.",
                category="general",
            )
        ]

        predictions = RuleEngine(rules).evaluate(chart)

        self.assertEqual(1, len(predictions))
        self.assertEqual("Case-insensitive typed aspect match succeeded.", predictions[0]["text"])

    def test_evaluate_supports_mixed_chart_and_aspect_conditions(self) -> None:
        chart = [
            ChartData(user_id=1, planet_name="Saturn", sign="Gemini", house=3, degree=10.0),
            ChartData(user_id=1, planet_name="Moon", sign="Leo", house=5, degree=12.0),
        ]
        rules = [
            Rule(
                condition_json='{"AND": [{"planet": "Saturn", "house": 3}, {"from_planet": "Saturn", "to_planet": "Moon", "to_house": 5, "aspect_type": "drishti"}]}',
                result_text="Saturn in 3rd aspects Moon in 5th.",
                category="general",
            )
        ]

        predictions = RuleEngine(rules).evaluate(chart)

        self.assertEqual(1, len(predictions))
        self.assertEqual("Saturn in 3rd aspects Moon in 5th.", predictions[0]["text"])

    def test_evaluate_supports_nested_typed_aspect_conditions(self) -> None:
        chart = [
            ChartData(user_id=1, planet_name="Saturn", sign="Gemini", house=3, degree=10.0),
            ChartData(user_id=1, planet_name="Moon", sign="Leo", house=5, degree=12.0),
        ]
        rules = [
            Rule(
                condition_json='{"AND": [{"planet": "Saturn", "house": 3}, {"type": "aspect", "from": "Saturn", "to": "Moon"}]}',
                result_text="Nested typed aspect condition matched.",
                category="general",
            )
        ]

        predictions = RuleEngine(rules).evaluate(chart)

        self.assertEqual(1, len(predictions))
        self.assertEqual("Nested typed aspect condition matched.", predictions[0]["text"])

    def test_evaluate_rejects_typed_aspect_condition_when_no_aspects_match(self) -> None:
        rules = [
            Rule(
                condition_json='{"type": "aspect", "from": "Jupiter", "to": "Moon"}',
                result_text="This typed aspect should not match.",
                category="general",
            )
        ]

        predictions = RuleEngine(rules).evaluate(self.chart, aspects=[])

        self.assertEqual([], predictions)

    def test_evaluate_computes_aspects_once_for_multiple_typed_aspect_rules(self) -> None:
        chart = [
            ChartData(user_id=1, planet_name="Saturn", sign="Gemini", house=3, degree=10.0),
            ChartData(user_id=1, planet_name="Moon", sign="Leo", house=5, degree=12.0),
        ]
        rules = [
            Rule(
                condition_json='{"type": "aspect", "from": "Saturn", "to": "Moon"}',
                result_text="First typed aspect match.",
                category="general",
            ),
            Rule(
                condition_json='{"type": "aspect", "from": "Saturn", "to": "Moon"}',
                result_text="Second typed aspect match.",
                category="general",
            ),
        ]

        with patch("app.engine.rule_engine.calculate_aspects", return_value=[{"from_planet": "Saturn", "to_planet": "Moon", "from_house": 3, "to_house": 5, "aspect_type": "drishti"}]) as mock_calculate_aspects:
            predictions = RuleEngine(rules).evaluate(chart)

        self.assertEqual(2, len(predictions))
        self.assertEqual(1, mock_calculate_aspects.call_count)

    def test_evaluate_supports_in_kendra_conditions(self) -> None:
        rules = [
            Rule(
                condition_json='{"type": "in_kendra", "planet": "Moon"}',
                result_text="Moon is in a kendra house.",
                category="general",
            )
        ]

        predictions = RuleEngine(rules).evaluate(self.chart)

        self.assertEqual(1, len(predictions))
        self.assertEqual("Moon is in a kendra house.", predictions[0]["text"])

    def test_evaluate_supports_case_insensitive_in_kendra_with_dict_rows(self) -> None:
        chart = [
            {"planet_name": "jupiter", "house": 4},
            {"planet_name": "Moon", "house": 10},
        ]
        rules = [
            Rule(
                condition_json='{"type": "in_kendra", "planet": "JUPITER"}',
                result_text="Jupiter is in a kendra house.",
                category="general",
            )
        ]

        predictions = RuleEngine(rules).evaluate(chart)

        self.assertEqual(1, len(predictions))
        self.assertEqual("Jupiter is in a kendra house.", predictions[0]["text"])

    def test_evaluate_rejects_in_kendra_when_planet_is_missing_or_house_invalid(self) -> None:
        chart = [
            {"planet_name": "Jupiter", "house": "not-a-house"},
        ]
        rules = [
            Rule(
                condition_json='{"type": "in_kendra", "planet": "Jupiter"}',
                result_text="This kendra rule should not match.",
                category="general",
            )
        ]

        predictions = RuleEngine(rules).evaluate(chart)

        self.assertEqual([], predictions)

    def test_evaluate_supports_relative_house_conditions(self) -> None:
        rules = [
            Rule(
                condition_json='{"type": "relative_house", "from": "Moon", "to": "Jupiter", "houses": [5]}',
                result_text="Jupiter is 5th from Moon.",
                category="general",
            )
        ]

        predictions = RuleEngine(rules).evaluate(self.chart)

        self.assertEqual(1, len(predictions))
        self.assertEqual("Jupiter is 5th from Moon.", predictions[0]["text"])
        self.assertIn("trace", predictions[0])
        self.assertTrue(any("relative house =" in line.lower() for line in predictions[0]["trace"]))

    def test_evaluate_supports_case_insensitive_relative_house_with_dict_rows(self) -> None:
        chart = [
            {"planet_name": "moon", "house": 10},
            {"Planet": "JUPITER", "House": 1},
        ]
        rules = [
            Rule(
                condition_json='{"type": "relative_house", "from": "MOON", "to": "jupiter", "houses": [4]}',
                result_text="Jupiter is 4th from Moon.",
                category="general",
            )
        ]

        predictions = RuleEngine(rules).evaluate(chart)

        self.assertEqual(1, len(predictions))
        self.assertEqual("Jupiter is 4th from Moon.", predictions[0]["text"])

    def test_evaluate_rejects_relative_house_when_planet_is_missing_or_house_invalid(self) -> None:
        chart = [
            {"planet_name": "Moon", "house": "bad-house"},
            {"planet_name": "Jupiter"},
        ]
        rules = [
            Rule(
                condition_json='{"type": "relative_house", "from": "Moon", "to": "Jupiter", "houses": [1, 4, 7, 10]}',
                result_text="This relative-house rule should not match.",
                category="general",
            )
        ]

        predictions = RuleEngine(rules).evaluate(chart)

        self.assertEqual([], predictions)

    def test_evaluate_supports_conjunction_conditions(self) -> None:
        chart = [
            ChartData(user_id=1, planet_name="Moon", sign="Cancer", house=4, degree=12.5),
            ChartData(user_id=1, planet_name="Jupiter", sign="Cancer", house=4, degree=5.0),
            ChartData(user_id=1, planet_name="Venus", sign="Libra", house=7, degree=18.0),
        ]
        rules = [
            Rule(
                condition_json='{"type": "conjunction", "planets": ["Moon", "Jupiter"]}',
                result_text="Moon and Jupiter are conjunct.",
                category="general",
            )
        ]

        predictions = RuleEngine(rules).evaluate(chart)

        self.assertEqual(1, len(predictions))
        self.assertEqual("Moon and Jupiter are conjunct.", predictions[0]["text"])

    def test_evaluate_supports_case_insensitive_conjunction_with_dict_rows(self) -> None:
        chart = [
            {"planet_name": "moon", "house": 4},
            {"Planet": "JUPITER", "House": 4},
            {"planet": "Venus", "house": 7},
        ]
        rules = [
            Rule(
                condition_json='{"type": "conjunction", "planets": ["Moon", "jupiter"]}',
                result_text="Case-insensitive conjunction matched.",
                category="general",
            )
        ]

        predictions = RuleEngine(rules).evaluate(chart)

        self.assertEqual(1, len(predictions))
        self.assertEqual("Case-insensitive conjunction matched.", predictions[0]["text"])

    def test_evaluate_rejects_conjunction_when_planets_are_not_in_same_house(self) -> None:
        rules = [
            Rule(
                condition_json='{"type": "conjunction", "planets": ["Moon", "Jupiter"]}',
                result_text="This conjunction should not match.",
                category="general",
            )
        ]

        predictions = RuleEngine(rules).evaluate(self.chart)

        self.assertEqual([], predictions)

    def test_evaluate_rejects_conjunction_when_planet_is_missing_or_house_invalid(self) -> None:
        chart = [
            {"planet_name": "Moon", "house": "not-a-house"},
            {"planet_name": "Jupiter"},
        ]
        rules = [
            Rule(
                condition_json='{"type": "conjunction", "planets": ["moon", "jupiter"]}',
                result_text="This conjunction should not match.",
                category="general",
            )
        ]

        predictions = RuleEngine(rules).evaluate(chart)

        self.assertEqual([], predictions)

    def test_get_planet_data_returns_normalized_row_for_chart_object(self) -> None:
        data = RuleEngine.get_planet_data(self.chart, "mOoN")

        self.assertIsNotNone(data)
        self.assertEqual("moon", data["planet_name"])
        self.assertEqual("Cancer", data["sign"])
        self.assertEqual(10, data["house"])
        self.assertIsInstance(data["raw"], ChartData)

    def test_get_planet_house_handles_dict_rows_and_invalid_house(self) -> None:
        chart = [
            {"planet_name": "Jupiter", "house": "invalid"},
            {"Planet": "Moon", "House": 4},
        ]

        self.assertIsNone(RuleEngine.get_planet_house(chart, "jupiter"))
        self.assertEqual(4, RuleEngine.get_planet_house(chart, "MOON"))


if __name__ == "__main__":
    unittest.main()
