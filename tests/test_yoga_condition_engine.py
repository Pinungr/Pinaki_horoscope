from __future__ import annotations

import unittest
from unittest.mock import patch

from core.yoga.condition_engine import ConditionContext, ConditionEngine
from core.yoga.models import ChartSnapshot


class YogaConditionEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = ConditionEngine()

    def test_evaluate_condition_supports_conjunction(self) -> None:
        chart = ChartSnapshot.from_rows(
            [
                {"planet_name": "Moon", "house": 4, "sign": "Cancer"},
                {"planet_name": "Jupiter", "house": 4, "sign": "Cancer"},
                {"planet_name": "Mars", "house": 7, "sign": "Libra"},
            ]
        )

        matched = self.engine.evaluate_condition(
            {"type": "conjunction", "planets": ["moon", "JUPITER"]},
            chart,
        )

        self.assertTrue(matched)

    def test_evaluate_condition_rejects_conjunction_when_planet_is_missing(self) -> None:
        chart = ChartSnapshot.from_rows([{"planet_name": "Moon", "house": 4, "sign": "Cancer"}])

        matched = self.engine.evaluate_condition(
            {"type": "conjunction", "planets": ["Moon", "Jupiter"]},
            chart,
        )

        self.assertFalse(matched)

    def test_evaluate_condition_supports_kendra_from_moon(self) -> None:
        chart = ChartSnapshot.from_rows(
            [
                {"planet_name": "Moon", "house": 1, "sign": "Aries"},
                {"planet_name": "Jupiter", "house": 7, "sign": "Libra"},
            ]
        )

        matched = self.engine.evaluate_condition(
            {"type": "kendra_from_moon", "planet": "jupiter"},
            chart,
        )

        self.assertTrue(matched)

    def test_evaluate_condition_supports_planet_in_house(self) -> None:
        chart = ChartSnapshot.from_rows([{"planet_name": "Saturn", "house": 10, "sign": "Capricorn"}])

        matched = self.engine.evaluate_condition(
            {"type": "planet_in_house", "planet": "SATURN", "houses": [1, 4, 7, 10]},
            chart,
        )

        self.assertTrue(matched)

    def test_evaluate_condition_supports_mutual_exchange(self) -> None:
        chart = ChartSnapshot.from_rows(
            [
                {"planet_name": "Mars", "house": 2, "sign": "Taurus"},
                {"planet_name": "Venus", "house": 1, "sign": "Aries"},
            ]
        )

        matched = self.engine.evaluate_condition(
            {"type": "mutual_exchange", "planets": ["mars", "venus"]},
            chart,
        )

        self.assertTrue(matched)

    def test_evaluate_condition_supports_aspect_relation(self) -> None:
        chart = ChartSnapshot.from_rows(
            [
                {"planet_name": "Saturn", "house": 3, "sign": "Gemini"},
                {"planet_name": "Moon", "house": 5, "sign": "Leo"},
            ]
        )

        matched = self.engine.evaluate_condition(
            {"type": "aspect_relation", "from": "saturn", "to": "MOON"},
            chart,
        )

        self.assertTrue(matched)

    def test_evaluate_condition_rejects_aspect_relation_when_missing(self) -> None:
        chart = ChartSnapshot.from_rows(
            [
                {"planet_name": "Saturn", "house": 3, "sign": "Gemini"},
                {"planet_name": "Moon", "house": 5, "sign": "Leo"},
            ]
        )

        matched = self.engine.evaluate_condition(
            {"type": "aspect_relation", "from": "Jupiter", "to": "Moon"},
            chart,
        )

        self.assertFalse(matched)

    def test_evaluate_conditions_mode_all(self) -> None:
        chart = ChartSnapshot.from_rows(
            [
                {"planet_name": "Moon", "house": 4, "sign": "Cancer"},
                {"planet_name": "Jupiter", "house": 4, "sign": "Cancer"},
            ]
        )

        matched = self.engine.evaluate_conditions(
            [
                {"type": "conjunction", "planets": ["Moon", "Jupiter"]},
                {"type": "planet_in_house", "planet": "Moon", "house": 4},
            ],
            chart,
        )

        self.assertTrue(matched)

    def test_evaluate_conditions_mode_any(self) -> None:
        chart = ChartSnapshot.from_rows([{"planet_name": "Moon", "house": 1, "sign": "Aries"}])

        matched = self.engine.evaluate_conditions(
            [
                {"type": "planet_in_house", "planet": "Moon", "house": 12},
                {"type": "planet_in_house", "planet": "Moon", "house": 1},
            ],
            chart,
            mode="any",
        )

        self.assertTrue(matched)

    def test_evaluate_conditions_calculates_aspects_once(self) -> None:
        chart = ChartSnapshot.from_rows(
            [
                {"planet_name": "Saturn", "house": 3, "sign": "Gemini"},
                {"planet_name": "Moon", "house": 5, "sign": "Leo"},
            ]
        )

        mock_aspects = [
            {
                "from_planet": "Saturn",
                "to_planet": "Moon",
                "from_house": 3,
                "to_house": 5,
                "aspect_type": "drishti",
            }
        ]

        with patch("core.yoga.condition_engine.calculate_aspects", return_value=mock_aspects) as mock_calculate:
            matched = self.engine.evaluate_conditions(
                [
                    {"type": "aspect_relation", "from": "Saturn", "to": "Moon"},
                    {"type": "aspect_relation", "from": "Saturn", "to": "Moon"},
                ],
                chart,
            )

        self.assertTrue(matched)
        self.assertEqual(1, mock_calculate.call_count)

    def test_evaluate_conditions_accepts_explicit_context(self) -> None:
        chart = ChartSnapshot.from_rows(
            [
                {"planet_name": "Saturn", "house": 3, "sign": "Gemini"},
                {"planet_name": "Moon", "house": 5, "sign": "Leo"},
            ]
        )
        context = ConditionContext(
            chart=chart,
            _aspects=[
                {
                    "from_planet": "Saturn",
                    "to_planet": "Moon",
                    "from_house": 3,
                    "to_house": 5,
                    "aspect_type": "drishti",
                }
            ],
        )

        with patch("core.yoga.condition_engine.calculate_aspects") as mock_calculate:
            matched = self.engine.evaluate_conditions(
                [{"type": "aspect_relation", "from": "Saturn", "to": "Moon"}],
                chart,
                context=context,
            )

        self.assertTrue(matched)
        self.assertEqual(0, mock_calculate.call_count)

    def test_evaluate_conditions_with_trace_returns_entries(self) -> None:
        chart = ChartSnapshot.from_rows(
            [
                {"planet_name": "Moon", "house": 4, "sign": "Cancer"},
                {"planet_name": "Jupiter", "house": 4, "sign": "Cancer"},
            ]
        )

        matched, trace = self.engine.evaluate_conditions_with_trace(
            [{"type": "conjunction", "planets": ["Moon", "Jupiter"]}],
            chart,
        )

        self.assertTrue(matched)
        self.assertEqual(1, len(trace))
        self.assertEqual("conjunction", trace[0]["type"])
        self.assertTrue(trace[0]["ok"])
        self.assertIn("elapsed_ms", trace[0])


    def test_evaluate_condition_supports_house_lord_relation_match(self) -> None:
        # Ascendant in Aries → house 7 sign is Libra → lord is Venus.
        # Venus placed in house 1 → matches in_houses=[1, 4, 7, 10].
        chart = ChartSnapshot.from_rows(
            [
                {"planet_name": "Ascendant", "house": 1, "sign": "Aries"},
                {"planet_name": "Venus", "house": 1, "sign": "Aries"},
            ]
        )

        matched = self.engine.evaluate_condition(
            {"type": "house_lord_relation", "of_house": 7, "in_houses": [1, 4, 7, 10]},
            chart,
        )

        self.assertTrue(matched)

    def test_evaluate_condition_rejects_house_lord_relation_when_lord_elsewhere(self) -> None:
        # Ascendant in Aries → house 7 sign is Libra → lord is Venus.
        # Venus placed in house 6 → NOT in [1, 4, 7, 10].
        chart = ChartSnapshot.from_rows(
            [
                {"planet_name": "Ascendant", "house": 1, "sign": "Aries"},
                {"planet_name": "Venus", "house": 6, "sign": "Virgo"},
            ]
        )

        matched = self.engine.evaluate_condition(
            {"type": "house_lord_relation", "of_house": 7, "in_houses": [1, 4, 7, 10]},
            chart,
        )

        self.assertFalse(matched)

    def test_evaluate_condition_rejects_house_lord_relation_without_ascendant(self) -> None:
        # No ascendant in chart → cannot resolve house sign → must return False, not crash.
        chart = ChartSnapshot.from_rows(
            [{"planet_name": "Venus", "house": 1, "sign": "Aries"}]
        )

        matched = self.engine.evaluate_condition(
            {"type": "house_lord_relation", "of_house": 7, "in_houses": [1]},
            chart,
        )

        self.assertFalse(matched)


if __name__ == "__main__":
    unittest.main()
