from __future__ import annotations

from pathlib import Path
import unittest

from core.engines.astrology_engine import UnifiedAstrologyEngine
from core.yoga.models import YogaDefinition
from core.yoga.yoga_engine import YogaEngine


class UnifiedAstrologyEngineTests(unittest.TestCase):
    @staticmethod
    def _build_engine_with_single_gajakesari() -> UnifiedAstrologyEngine:
        gajakesari = YogaDefinition.from_dict(
            {
                "id": "gajakesari_yoga",
                "conditions": [{"type": "conjunction", "planets": ["moon", "jupiter"]}],
                "prediction": {"en": "placeholder"},
            }
        )
        yoga_engine = YogaEngine(config_dir=Path("/nonexistent"), extra_definitions=[gajakesari])
        return UnifiedAstrologyEngine(yoga_engine=yoga_engine)

    def test_analyze_returns_unified_payload_shape(self) -> None:
        engine = self._build_engine_with_single_gajakesari()
        chart_data = [
            {"planet_name": "Ascendant", "sign": "Aries", "house": 1, "degree": 5.0},
            {"planet_name": "Moon", "sign": "Cancer", "house": 4, "degree": 10.0},
            {"planet_name": "Jupiter", "sign": "Cancer", "house": 4, "degree": 12.0},
            {"planet_name": "Sun", "sign": "Gemini", "house": 3, "degree": 15.0},
        ]

        result = engine.analyze(chart_data, dob="1990-01-01", language="en")

        self.assertIn("yogas", result)
        self.assertIn("strong_yogas", result)
        self.assertIn("weak_yogas", result)
        self.assertIn("dasha", result)
        self.assertIn("final_predictions", result)
        self.assertIn("confidence_score", result)

        self.assertEqual(1, len(result["yogas"]))
        self.assertEqual("gajakesari_yoga", result["yogas"][0]["id"])
        self.assertEqual(9, len(result["dasha"]["timeline"]))
        self.assertEqual(1, len(result["final_predictions"]))
        self.assertEqual("gajakesari_yoga", result["final_predictions"][0]["rule"])
        self.assertGreaterEqual(result["confidence_score"], 0)
        self.assertLessEqual(result["confidence_score"], 100)

    def test_analyze_handles_missing_moon_or_dob_for_dasha(self) -> None:
        engine = self._build_engine_with_single_gajakesari()
        chart_data = [
            {"planet_name": "Jupiter", "sign": "Cancer", "house": 4, "degree": 12.0},
        ]

        result = engine.analyze(chart_data, dob=None, language="en")

        self.assertEqual([], result["dasha"]["timeline"])
        self.assertIsNone(result["dasha"]["moon_longitude"])

    def test_analyze_can_include_condition_trace(self) -> None:
        engine = self._build_engine_with_single_gajakesari()
        chart_data = [
            {"planet_name": "Moon", "sign": "Cancer", "house": 4, "degree": 10.0},
            {"planet_name": "Jupiter", "sign": "Cancer", "house": 4, "degree": 12.0},
        ]

        result = engine.analyze(chart_data, dob="1990-01-01", language="en", include_trace=True)

        self.assertEqual(1, len(result["yogas"]))
        self.assertIn("trace", result["yogas"][0])
        self.assertIn("trace_summary", result["yogas"][0])
        self.assertGreater(result["yogas"][0]["trace_summary"]["total"], 0)

    def test_analyze_returns_empty_prediction_list_when_no_yoga_matches(self) -> None:
        engine = self._build_engine_with_single_gajakesari()
        chart_data = [
            {"planet_name": "Moon", "sign": "Aries", "house": 1, "degree": 10.0},
            {"planet_name": "Jupiter", "sign": "Taurus", "house": 2, "degree": 12.0},
        ]

        result = engine.analyze(chart_data, dob="1990-01-01", language="en")

        self.assertEqual([], result["yogas"])
        self.assertEqual([], result["strong_yogas"])
        self.assertEqual([], result["weak_yogas"])
        self.assertEqual([], result["final_predictions"])


if __name__ == "__main__":
    unittest.main()
