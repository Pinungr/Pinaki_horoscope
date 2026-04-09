from __future__ import annotations

from datetime import date
import unittest
from unittest.mock import patch

from core.predictions.prediction_service import PredictionService
from core.yoga.models import ChartSnapshot


class ContextualPredictionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = PredictionService()

    def test_get_house_area_mapping(self) -> None:
        self.assertEqual("career", self.service.get_house_area(10))
        self.assertEqual("marriage", self.service.get_house_area("7"))
        self.assertEqual("general", self.service.get_house_area("invalid"))

    def test_extract_prediction_context_uses_explicit_house(self) -> None:
        yoga = {"id": "gajakesari_yoga", "house": 7, "strength_level": "medium"}

        chart_data = [{"planet_name": "Ascendant", "sign": "Aries", "house": 1, "degree": 0.0}]
        context = self.service.extract_prediction_context(yoga, chart_data=chart_data)

        self.assertEqual("gajakesari_yoga", context["yoga"])
        self.assertEqual(7, context["house"])
        self.assertEqual("marriage", context["area"])
        self.assertEqual("medium", context["strength"])
        self.assertIn("house_lord", context)
        self.assertEqual("venus", context["house_lord"]["lord"])
        self.assertIn("house_lord_details", context)

    def test_extract_prediction_context_uses_key_planet_house_from_rows(self) -> None:
        yoga = {"id": "gajakesari_yoga", "key_planets": ["Jupiter"], "strength_level": "strong"}
        chart_data = [{"planet_name": "Jupiter", "house": 10}]

        context = self.service.extract_prediction_context(yoga, chart_data)

        self.assertEqual(10, context["house"])
        self.assertEqual("career", context["area"])
        self.assertEqual("strong", context["strength"])

    def test_extract_prediction_context_supports_chart_snapshot(self) -> None:
        yoga = {"id": "gajakesari_yoga", "key_planets": ["moon"], "strength_level": "weak"}
        snapshot = ChartSnapshot.from_rows(
            [
                {"planet_name": "Moon", "sign": "Cancer", "house": 4, "degree": 12.0},
            ]
        )

        context = self.service.extract_prediction_context(yoga, snapshot)

        self.assertEqual(4, context["house"])
        self.assertEqual("home", context["area"])
        self.assertEqual("weak", context["strength"])

    def test_generate_contextual_prediction_returns_structured_dynamic_payload(self) -> None:
        yoga = {"id": "gajakesari_yoga", "key_planets": ["Jupiter"], "strength_level": "strong"}
        chart_data = [
            {"planet_name": "Ascendant", "sign": "Aries", "house": 1, "degree": 0.0},
            {"planet_name": "Jupiter", "house": 10, "sign": "Capricorn", "degree": 6.0},
        ]

        payload = self.service.generate_contextual_prediction(yoga, chart_data, language="en")

        self.assertEqual("gajakesari_yoga", payload["yoga"])
        self.assertEqual("career", payload["area"])
        self.assertEqual("strong", payload["strength"])
        self.assertEqual(10, payload["house"])
        self.assertIn("house_lord", payload)
        self.assertIn("career", payload["text"].lower())
        self.assertIn("powerful", payload["text"].lower())

    def test_get_house_lord_details_returns_complete_structure(self) -> None:
        chart_data = [{"planet_name": "Ascendant", "sign": "Libra", "house": 1, "degree": 0.0}]
        details = self.service.get_house_lord_details(chart_data)

        self.assertEqual(set(range(1, 13)), set(details.keys()))
        self.assertEqual("saturn", details[4]["lord"])
        self.assertEqual("saturn", details[5]["lord"])

    def test_generate_contextual_supports_explicit_strength_input(self) -> None:
        yoga = {"id": "gajakesari_yoga", "key_planets": ["Moon"]}
        chart_data = [{"planet_name": "Moon", "house": 7}]

        payload = self.service.generate_contextual(
            chart=chart_data,
            yoga=yoga,
            strength={"level": "weak", "score": 32},
            language="en",
        )

        self.assertEqual("marriage", payload["area"])
        self.assertEqual("weak", payload["strength"])
        self.assertIn("relationships", payload["text"].lower())
        self.assertIn("mild", payload["text"].lower())

    def test_map_yoga_to_planets_extracts_known_planets(self) -> None:
        yoga = {
            "id": "gajakesari_yoga",
            "key_planets": ["Moon", "Jupiter"],
            "from": "Saturn",
            "to": "Moon",
        }

        planets = self.service.map_yoga_to_planets(yoga)

        self.assertEqual(["moon", "jupiter", "saturn"], planets)

    def test_evaluate_dasha_relevance_marks_high_when_mahadasha_matches_yoga_planet(self) -> None:
        yoga = {"id": "gajakesari_yoga", "key_planets": ["Jupiter", "Moon"]}
        dasha_data = {
            "timeline": [
                {"planet": "Jupiter", "start": "2020-01-01", "end": "2036-01-01"},
            ]
        }

        relevance = self.service.evaluate_dasha_relevance(
            yoga,
            dasha_data,
            reference_date=date(2026, 4, 8),
        )

        self.assertEqual("Jupiter", relevance["mahadasha"])
        self.assertEqual("high", relevance["relevance"])
        self.assertIn("jupiter", relevance["matched_planets"])
        self.assertGreater(relevance["score_multiplier"], 1.0)

    def test_evaluate_dasha_relevance_marks_medium_when_only_antardasha_matches(self) -> None:
        yoga = {"id": "venus_focus", "key_planets": ["Venus"]}
        dasha_data = {
            "timeline": [
                {
                    "planet": "Saturn",
                    "antardasha": "Venus",
                    "start": "2020-01-01",
                    "end": "2039-01-01",
                },
            ]
        }

        relevance = self.service.evaluate_dasha_relevance(
            yoga,
            dasha_data,
            reference_date=date(2026, 4, 8),
        )

        self.assertEqual("Saturn", relevance["mahadasha"])
        self.assertEqual("Venus", relevance["antardasha"])
        self.assertEqual("medium", relevance["relevance"])
        self.assertIn("venus", relevance["matched_planets"])

    def test_evaluate_dasha_relevance_includes_d10_fields_for_career(self) -> None:
        yoga = {"id": "career_focus", "key_planets": ["Saturn"], "house": 10}
        dasha_data = {
            "timeline": [
                {
                    "planet": "Saturn",
                    "start": "2020-01-01",
                    "end": "2039-01-01",
                },
            ]
        }

        with patch.object(
            self.service,
            "evaluate_d10_career_validation",
            return_value={"status": "confirm", "factors": ["D10 10th lord well placed."], "multiplier": 1.12, "score": 1.5},
        ):
            relevance = self.service.evaluate_dasha_relevance(
                yoga,
                dasha_data,
                chart_data=[{"planet_name": "Ascendant", "sign": "Aries", "house": 1, "degree": 0.0}],
                prediction_context={"area": "career", "relevant_houses": [10], "house_lord_details": {10: {"lord": "saturn"}}},
                reference_date=date(2026, 4, 8),
            )

        self.assertEqual("confirm", relevance["d10_status"])
        self.assertIn("D10 10th lord well placed.", relevance["d10_evidence"])
        self.assertGreater(relevance["score_multiplier"], relevance["dasha_multiplier"])

    def test_evaluate_dasha_relevance_reduces_multiplier_when_d10_conflicts(self) -> None:
        yoga = {"id": "career_focus", "key_planets": ["Saturn"], "house": 10}
        dasha_data = {
            "timeline": [
                {"planet": "Saturn", "start": "2020-01-01", "end": "2039-01-01"},
            ]
        }

        with patch.object(
            self.service,
            "evaluate_d10_career_validation",
            return_value={"status": "conflict", "factors": ["D1 10th lord stressed in D10."], "multiplier": 0.86, "score": -1.3},
        ):
            relevance = self.service.evaluate_dasha_relevance(
                yoga,
                dasha_data,
                chart_data=[{"planet_name": "Ascendant", "sign": "Aries", "house": 1, "degree": 0.0}],
                prediction_context={"area": "career", "relevant_houses": [10], "house_lord_details": {10: {"lord": "saturn"}}},
                reference_date=date(2026, 4, 8),
            )

        self.assertEqual("conflict", relevance["d10_status"])
        self.assertLess(relevance["score_multiplier"], relevance["dasha_multiplier"])

    def test_evaluate_transit_trigger_amplifies_when_reinforcing_promise_and_dasha(self) -> None:
        yoga = {"id": "career_yoga", "key_planets": ["Jupiter"], "area": "career", "house": 10}
        prediction_context = {
            "area": "career",
            "relevant_houses": [10],
            "yoga_planets": ["jupiter"],
            "karakas": ["saturn"],
            "house_lord": {"lord": "saturn"},
            "house_lord_details": {
                10: {"lord": "saturn", "placement": {"house": 4}},
            },
        }
        transit_data = {
            "reference": "both",
            "transit_matrix": {
                "jupiter": {
                    "from_lagna": {"house_position": 10},
                    "from_moon": {"house_position": 7},
                },
                "saturn": {
                    "from_lagna": {"house_position": 10},
                    "from_moon": {"house_position": 10},
                },
            },
        }
        dasha = {"mahadasha": "Jupiter", "antardasha": "Saturn"}

        trigger = self.service.evaluate_transit_trigger(
            yoga,
            transit_data,
            dasha_relevance=dasha,
            prediction_context=prediction_context,
        )

        self.assertGreater(trigger["score_multiplier"], 1.0)
        self.assertIn(trigger["trigger_level"], {"medium", "high"})
        self.assertEqual("amplifying", trigger["support_state"])
        self.assertTrue(trigger["matched_planets"])
        self.assertTrue(any("matching current dasha lord" in row.lower() for row in trigger["source_factors"]))

    def test_evaluate_transit_trigger_suppresses_when_actor_in_challenging_houses(self) -> None:
        yoga = {"id": "career_yoga", "key_planets": ["Saturn"], "area": "career", "house": 10}
        prediction_context = {
            "area": "career",
            "relevant_houses": [10],
            "yoga_planets": ["saturn"],
            "karakas": ["saturn"],
            "house_lord": {"lord": "saturn"},
        }
        transit_data = {
            "reference": "both",
            "transit_matrix": {
                "saturn": {
                    "from_lagna": {"house_position": 8},
                    "from_moon": {"house_position": 12},
                }
            },
        }
        dasha = {"mahadasha": "Saturn", "antardasha": "Saturn"}

        trigger = self.service.evaluate_transit_trigger(
            yoga,
            transit_data,
            dasha_relevance=dasha,
            prediction_context=prediction_context,
        )

        self.assertLess(trigger["score_multiplier"], 1.0)
        self.assertEqual("suppressing", trigger["support_state"])
        self.assertFalse(trigger["trigger_now"])
        self.assertTrue(any("suppressing" in row.lower() for row in trigger["source_factors"]))

    def test_evaluate_d10_career_validation_confirm_for_strong_d1_and_d10(self) -> None:
        d10_stub = {
            "ascendant_sign": "aries",
            "rows": [
                {"planet_name": "Ascendant", "sign": "aries", "house": 1, "degree": 0.0},
                {"planet_name": "Saturn", "sign": "libra", "house": 7, "degree": 10.0},
                {"planet_name": "Sun", "sign": "leo", "house": 5, "degree": 5.0},
            ],
            "placements": {
                "ascendant": {"sign": "aries", "house": 1, "degree": 0.0},
                "saturn": {"sign": "libra", "house": 7, "degree": 10.0},
                "sun": {"sign": "leo", "house": 5, "degree": 5.0},
            },
        }
        context = {
            "area": "career",
            "relevant_houses": [10],
            "house_lord_details": {10: {"lord": "sun"}},
        }
        with patch.object(self.service._varga_engine, "get_d10_chart", return_value=d10_stub):
            result = self.service.evaluate_d10_career_validation(
                chart_data=[{"planet_name": "Ascendant", "sign": "Aries", "house": 1, "degree": 0.0}],
                prediction_context=context,
            )

        self.assertEqual("confirm", result["status"])
        self.assertGreater(result["multiplier"], 1.0)
        self.assertTrue(any("well placed" in factor.lower() for factor in result["factors"]))

    def test_evaluate_d10_career_validation_conflict_for_weak_d10(self) -> None:
        d10_stub = {
            "ascendant_sign": "aries",
            "rows": [
                {"planet_name": "Ascendant", "sign": "aries", "house": 1, "degree": 0.0},
                {"planet_name": "Saturn", "sign": "aries", "house": 1, "degree": 10.0},
                {"planet_name": "Sun", "sign": "libra", "house": 7, "degree": 5.0},
            ],
            "placements": {
                "ascendant": {"sign": "aries", "house": 1, "degree": 0.0},
                "saturn": {"sign": "aries", "house": 1, "degree": 10.0},
                "sun": {"sign": "libra", "house": 7, "degree": 5.0},
            },
        }
        context = {
            "area": "career",
            "relevant_houses": [10],
            "house_lord_details": {10: {"lord": "sun"}},
        }
        with patch.object(self.service._varga_engine, "get_d10_chart", return_value=d10_stub):
            result = self.service.evaluate_d10_career_validation(
                chart_data=[{"planet_name": "Ascendant", "sign": "Aries", "house": 1, "degree": 0.0}],
                prediction_context=context,
            )

        self.assertEqual("conflict", result["status"])
        self.assertLess(result["multiplier"], 1.0)
        self.assertTrue(any("weak" in factor.lower() or "stressed" in factor.lower() for factor in result["factors"]))

    def test_evaluate_d10_career_validation_returns_neutral_for_mixed_signals(self) -> None:
        d10_stub = {
            "ascendant_sign": "aries",
            "rows": [
                {"planet_name": "Ascendant", "sign": "aries", "house": 1, "degree": 0.0},
                {"planet_name": "Saturn", "sign": "capricorn", "house": 10, "degree": 10.0},
                {"planet_name": "Sun", "sign": "libra", "house": 7, "degree": 5.0},
            ],
            "placements": {
                "ascendant": {"sign": "aries", "house": 1, "degree": 0.0},
                "saturn": {"sign": "capricorn", "house": 10, "degree": 10.0},
                "sun": {"sign": "libra", "house": 7, "degree": 5.0},
            },
        }
        context = {
            "area": "career",
            "relevant_houses": [10],
            "house_lord_details": {10: {"lord": "sun"}},
        }
        with patch.object(self.service._varga_engine, "get_d10_chart", return_value=d10_stub):
            result = self.service.evaluate_d10_career_validation(
                chart_data=[{"planet_name": "Ascendant", "sign": "Aries", "house": 1, "degree": 0.0}],
                prediction_context=context,
            )

        self.assertEqual("neutral", result["status"])
        self.assertEqual(1.0, result["multiplier"])

    def test_evaluate_d10_career_validation_falls_back_to_neutral_when_missing(self) -> None:
        with patch.object(
            self.service._varga_engine,
            "get_d10_chart",
            return_value={"ascendant_sign": "", "rows": [], "placements": {}},
        ):
            result = self.service.evaluate_d10_career_validation(chart_data=[], prediction_context={"area": "career"})

        self.assertEqual("neutral", result["status"])
        self.assertEqual(1.0, result["multiplier"])
        self.assertTrue(result["factors"])


if __name__ == "__main__":
    unittest.main()
