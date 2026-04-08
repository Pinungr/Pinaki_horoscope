from __future__ import annotations

from datetime import date
import unittest

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

        context = self.service.extract_prediction_context(yoga, chart_data=[])

        self.assertEqual("gajakesari_yoga", context["yoga"])
        self.assertEqual(7, context["house"])
        self.assertEqual("marriage", context["area"])
        self.assertEqual("medium", context["strength"])

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
        chart_data = [{"planet_name": "Jupiter", "house": 10}]

        payload = self.service.generate_contextual_prediction(yoga, chart_data, language="en")

        self.assertEqual("gajakesari_yoga", payload["yoga"])
        self.assertEqual("career", payload["area"])
        self.assertEqual("strong", payload["strength"])
        self.assertIn("career", payload["text"].lower())
        self.assertIn("powerful", payload["text"].lower())

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


if __name__ == "__main__":
    unittest.main()
