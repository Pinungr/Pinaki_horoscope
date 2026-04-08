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

    def test_generate_full_analysis_returns_ui_ready_contract(self) -> None:
        engine = self._build_engine_with_single_gajakesari()
        chart_data = [
            {"planet_name": "Ascendant", "sign": "Aries", "house": 1, "degree": 5.0},
            {"planet_name": "Moon", "sign": "Cancer", "house": 4, "degree": 10.0},
            {"planet_name": "Jupiter", "sign": "Cancer", "house": 4, "degree": 12.0},
            {"planet_name": "Sun", "sign": "Gemini", "house": 3, "degree": 15.0},
        ]

        result = engine.generate_full_analysis(chart_data, language="en")

        self.assertIn("summary", result)
        self.assertIn("predictions", result)
        self.assertIn("meta", result)
        self.assertEqual(1, result["meta"]["total_yogas"])
        self.assertEqual(1, len(result["predictions"]))
        self.assertEqual("gajakesari yoga", result["predictions"][0]["yoga"].lower())
        self.assertIn("timing", result["predictions"][0])
        self.assertIn("relevance", result["predictions"][0]["timing"])
        self.assertIn("matched_planets", result["predictions"][0]["timing"])
        self.assertIn("time_focus", result["summary"])
        self.assertIn("refined_text", result["predictions"][0])
        self.assertEqual(result["predictions"][0]["text"], result["predictions"][0]["refined_text"])
        self.assertTrue(result["meta"]["generated_at"])

    def test_generate_full_analysis_adds_dasha_timing_and_boosts_score(self) -> None:
        class _StubDashaEngine:
            @staticmethod
            def calculate_dasha(_moon_longitude, _dob):
                return [
                    {
                        "planet": "Jupiter",
                        "antardasha": "Moon",
                        "start": "2020-01-01",
                        "end": "2036-01-01",
                    }
                ]

        gajakesari = YogaDefinition.from_dict(
            {
                "id": "gajakesari_yoga",
                "conditions": [{"type": "conjunction", "planets": ["moon", "jupiter"]}],
                "prediction": {"en": "placeholder"},
            }
        )
        yoga_engine = YogaEngine(config_dir=Path("/nonexistent"), extra_definitions=[gajakesari])
        engine = UnifiedAstrologyEngine(yoga_engine=yoga_engine, dasha_engine=_StubDashaEngine())

        chart_data = [
            {"planet_name": "Moon", "sign": "Cancer", "house": 4, "degree": 10.0},
            {"planet_name": "Jupiter", "sign": "Cancer", "house": 4, "degree": 12.0},
        ]

        baseline = engine.generate_full_analysis(chart_data, language="en")
        timed = engine.generate_full_analysis(chart_data, language="en", dob="1990-01-01")

        self.assertEqual(1, len(timed["predictions"]))
        self.assertEqual("high", timed["predictions"][0]["timing"]["relevance"])
        self.assertEqual("Jupiter", timed["predictions"][0]["timing"]["mahadasha"])
        self.assertIn("jupiter", timed["predictions"][0]["timing"]["matched_planets"])
        self.assertEqual(["home"], timed["summary"]["time_focus"])
        self.assertGreaterEqual(timed["predictions"][0]["score"], baseline["predictions"][0]["score"])
        self.assertIn("mahadasha", timed["predictions"][0]["text"].lower())
        self.assertIn("mahadasha", timed["predictions"][0]["refined_text"].lower())

    def test_generate_full_analysis_uses_ai_refiner_when_available(self) -> None:
        class _StubRefiner:
            def refine_predictions(self, predictions, summary, tone="professional"):
                rows = []
                for prediction in predictions:
                    row = dict(prediction)
                    row["refined_text"] = f"AI:{tone}:{row.get('text', '')}"
                    rows.append(row)
                return rows

        gajakesari = YogaDefinition.from_dict(
            {
                "id": "gajakesari_yoga",
                "conditions": [{"type": "conjunction", "planets": ["moon", "jupiter"]}],
                "prediction": {"en": "placeholder"},
            }
        )
        yoga_engine = YogaEngine(config_dir=Path("/nonexistent"), extra_definitions=[gajakesari])
        engine = UnifiedAstrologyEngine(yoga_engine=yoga_engine, ai_refiner=_StubRefiner())

        chart_data = [
            {"planet_name": "Moon", "sign": "Cancer", "house": 4, "degree": 10.0},
            {"planet_name": "Jupiter", "sign": "Cancer", "house": 4, "degree": 12.0},
        ]
        result = engine.generate_full_analysis(chart_data, language="en", tone="friendly")

        self.assertEqual(1, len(result["predictions"]))
        self.assertIn("AI:friendly:", result["predictions"][0]["refined_text"])


if __name__ == "__main__":
    unittest.main()
