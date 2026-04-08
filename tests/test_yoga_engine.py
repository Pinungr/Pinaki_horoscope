from __future__ import annotations

import unittest
from pathlib import Path

from core.yoga.yoga_engine import YogaEngine, YogaResult
from core.yoga.models import ChartSnapshot, YogaDefinition


# ---------------------------------------------------------------------------
# Helper - build an inline engine from embedded definitions (no JSON needed)
# ---------------------------------------------------------------------------

def _engine_from_defs(*payloads: dict) -> YogaEngine:
    """Creates a YogaEngine pre-loaded with explicit definitions."""
    defs = [YogaDefinition.from_dict(p) for p in payloads]
    # Pass a non-existent config dir so no JSON is loaded; inject defs via extra_definitions
    engine = YogaEngine(config_dir=Path("/nonexistent"), extra_definitions=defs)
    return engine


# ---------------------------------------------------------------------------
# Configuration-file loading
# ---------------------------------------------------------------------------

class YogaEngineLoadTests(unittest.TestCase):

    def test_engine_loads_json_configs(self) -> None:
        """Engine must load at least the bundled chandra_yogas + pancha_mahapurusha."""
        engine = YogaEngine()
        self.assertGreater(len(engine.loaded_yoga_ids), 0)
        self.assertIn("gajakesari_yoga", engine.loaded_yoga_ids)
        self.assertIn("hamsa_yoga", engine.loaded_yoga_ids)
        self.assertIn("budhaditya_yoga", engine.loaded_yoga_ids)

    def test_engine_tolerates_missing_config_dir(self) -> None:
        engine = YogaEngine(config_dir=Path("/no/such/dir"))
        self.assertEqual([], engine.loaded_yoga_ids)

    def test_engine_accepts_extra_definitions(self) -> None:
        extra = YogaDefinition.from_dict({
            "id": "test_yoga_custom",
            "conditions": [{"type": "planet_in_house", "planet": "sun", "houses": [1]}],
            "prediction": {"en": "Test yoga fired."},
        })
        engine = YogaEngine(config_dir=Path("/nonexistent"), extra_definitions=[extra])
        self.assertIn("test_yoga_custom", engine.loaded_yoga_ids)


# ---------------------------------------------------------------------------
# Gajakesari Yoga (kendra_from_moon)
# ---------------------------------------------------------------------------

class GajakesariYogaTests(unittest.TestCase):

    def setUp(self) -> None:
        self.engine = YogaEngine()

    def test_gajakesari_detected_when_jupiter_kendra_from_moon(self) -> None:
        chart = ChartSnapshot.from_rows([
            {"planet_name": "Moon",    "house": 1, "sign": "Aries",  "degree": 5.0},
            {"planet_name": "Jupiter", "house": 4, "sign": "Cancer", "degree": 20.0},
        ])
        result = self.engine.evaluate_one("gajakesari_yoga", chart)
        self.assertIsNotNone(result)
        self.assertTrue(result.detected)
        self.assertGreater(len(result.prediction), 0)

    def test_gajakesari_not_detected_when_jupiter_not_kendra(self) -> None:
        chart = ChartSnapshot.from_rows([
            {"planet_name": "Moon",    "house": 1, "sign": "Aries", "degree": 5.0},
            {"planet_name": "Jupiter", "house": 3, "sign": "Gemini", "degree": 10.0},
        ])
        result = self.engine.evaluate_one("gajakesari_yoga", chart)
        self.assertFalse(result.detected)


# ---------------------------------------------------------------------------
# Pancha Mahapurusha (hamsa_yoga as representative case)
# ---------------------------------------------------------------------------

class HamsaYogaTests(unittest.TestCase):

    def setUp(self) -> None:
        self.engine = YogaEngine()

    def test_hamsa_detected_jupiter_exalted_kendra(self) -> None:
        # Jupiter exalted in Cancer = house 4 kendra
        # Include Sun (10th house) and Ascendant (Aries) for context
        chart = ChartSnapshot.from_rows([
            {"planet_name": "Jupiter", "house": 4, "sign": "Cancer", "degree": 15.0, "absolute_longitude": 105.0},
            {"planet_name": "Sun", "house": 10, "sign": "Capricorn", "degree": 0.0, "absolute_longitude": 270.0},
            {"planet_name": "Ascendant", "house": 1, "sign": "Aries", "degree": 0.0, "absolute_longitude": 0.0},
        ])
        result = self.engine.evaluate_one("hamsa_yoga", chart)
        self.assertTrue(result.detected)
        self.assertIn(result.strength_level, ("medium", "strong"))

    def test_hamsa_not_detected_when_jupiter_not_dignified(self) -> None:
        # Jupiter in kendra but in Capricorn (debilitation) - fails dignity condition
        chart = ChartSnapshot.from_rows([
            {"planet_name": "Jupiter", "house": 10, "sign": "Capricorn", "degree": 5.0},
        ])
        result = self.engine.evaluate_one("hamsa_yoga", chart)
        self.assertFalse(result.detected)


# ---------------------------------------------------------------------------
# Chandra Moon-relative yogas
# ---------------------------------------------------------------------------

class ChandraMoonRelativeTests(unittest.TestCase):

    def setUp(self) -> None:
        self.engine = YogaEngine()

    def test_sunapha_detected_when_mars_in_2nd_from_moon(self) -> None:
        # Moon house 3, Mars house 4 (2nd from Moon)
        chart = ChartSnapshot.from_rows([
            {"planet_name": "Moon", "house": 3, "sign": "Gemini", "degree": 10.0},
            {"planet_name": "Mars", "house": 4, "sign": "Cancer", "degree": 5.0},
        ])
        result = self.engine.evaluate_one("sunapha_yoga", chart)
        self.assertTrue(result.detected)

    def test_sunapha_not_detected_when_only_sun_in_2nd_from_moon(self) -> None:
        # Sun is excluded from Sunapha
        chart = ChartSnapshot.from_rows([
            {"planet_name": "Moon", "house": 3, "sign": "Gemini", "degree": 10.0},
            {"planet_name": "Sun",  "house": 4, "sign": "Cancer",  "degree": 5.0},
        ])
        result = self.engine.evaluate_one("sunapha_yoga", chart)
        self.assertFalse(result.detected)

    def test_kemadruma_detected_when_moon_isolated(self) -> None:
        # Moon in house 6, no planets in 5th or 7th (excluding Sun/Rahu/Ketu)
        chart = ChartSnapshot.from_rows([
            {"planet_name": "Moon",    "house": 6, "sign": "Virgo",   "degree": 10.0},
            {"planet_name": "Sun",     "house": 5, "sign": "Leo",     "degree": 20.0},  # excluded
            {"planet_name": "Saturn",  "house": 2, "sign": "Taurus",  "degree": 5.0},  # not adjacent
        ])
        result = self.engine.evaluate_one("kemadruma_yoga", chart)
        self.assertTrue(result.detected)

    def test_kemadruma_not_detected_when_saturn_adjacent(self) -> None:
        # Saturn in 7th (adjacent to Moon in 6th)
        chart = ChartSnapshot.from_rows([
            {"planet_name": "Moon",   "house": 6, "sign": "Virgo", "degree": 10.0},
            {"planet_name": "Saturn", "house": 7, "sign": "Libra", "degree": 5.0},
        ])
        result = self.engine.evaluate_one("kemadruma_yoga", chart)
        self.assertFalse(result.detected)

    def test_adhi_yoga_detected_when_jupiter_in_6th_from_moon(self) -> None:
        # Moon house 1; Jupiter house 6 (6th from Moon)
        chart = ChartSnapshot.from_rows([
            {"planet_name": "Moon",    "house": 1, "sign": "Aries",       "degree": 5.0},
            {"planet_name": "Jupiter", "house": 6, "sign": "Virgo",       "degree": 10.0},
        ])
        result = self.engine.evaluate_one("adhi_yoga", chart)
        self.assertTrue(result.detected)


# ---------------------------------------------------------------------------
# Budhaditya Yoga
# ---------------------------------------------------------------------------

class BudhadityaYogaTests(unittest.TestCase):

    def setUp(self) -> None:
        self.engine = YogaEngine()

    def test_budhaditya_detected_when_sun_mercury_conjunction(self) -> None:
        chart = ChartSnapshot.from_rows([
            {"planet_name": "Sun",     "house": 1, "sign": "Aries", "degree": 10.0},
            {"planet_name": "Mercury", "house": 1, "sign": "Aries", "degree": 8.0},
        ])
        result = self.engine.evaluate_one("budhaditya_yoga", chart)
        self.assertTrue(result.detected)

    def test_budhaditya_not_detected_when_different_houses(self) -> None:
        chart = ChartSnapshot.from_rows([
            {"planet_name": "Sun",     "house": 1, "sign": "Aries",  "degree": 10.0},
            {"planet_name": "Mercury", "house": 2, "sign": "Taurus", "degree": 5.0},
        ])
        result = self.engine.evaluate_one("budhaditya_yoga", chart)
        self.assertFalse(result.detected)


# ---------------------------------------------------------------------------
# evaluate() bulk method
# ---------------------------------------------------------------------------

class YogaEngineBulkTests(unittest.TestCase):

    def setUp(self) -> None:
        self.engine = YogaEngine()

    def test_evaluate_returns_list_of_yoga_results(self) -> None:
        chart = ChartSnapshot.from_rows([
            {"planet_name": "Moon",    "house": 1, "sign": "Aries",  "degree": 5.0},
            {"planet_name": "Jupiter", "house": 4, "sign": "Cancer", "degree": 10.0},
        ])
        results = self.engine.evaluate(chart)
        self.assertIsInstance(results, list)
        self.assertTrue(all(isinstance(r, YogaResult) for r in results))

    def test_evaluate_detected_only_filters_correctly(self) -> None:
        chart = ChartSnapshot.from_rows([
            {"planet_name": "Moon",    "house": 1, "sign": "Aries",  "degree": 5.0},
            {"planet_name": "Jupiter", "house": 4, "sign": "Cancer", "degree": 10.0},
        ])
        results = self.engine.evaluate(chart, detected_only=True)
        self.assertTrue(all(r.detected for r in results))

    def test_evaluate_detected_results_are_sorted_by_strength(self) -> None:
        chart = ChartSnapshot.from_rows([
            {"planet_name": "Moon",    "house": 1, "sign": "Taurus", "degree": 5.0, "absolute_longitude": 35.0},
            {"planet_name": "Jupiter", "house": 4, "sign": "Cancer", "degree": 10.0, "absolute_longitude": 100.0},
            {"planet_name": "Mercury", "house": 4, "sign": "Cancer", "degree": 12.0, "absolute_longitude": 102.0},
            {"planet_name": "Sun", "house": 10, "sign": "Capricorn", "degree": 0.0, "absolute_longitude": 270.0},
            {"planet_name": "Ascendant", "house": 1, "sign": "Aries", "degree": 0.0, "absolute_longitude": 0.0},
        ])
        results = self.engine.evaluate(chart, detected_only=True)
        scores = [r.strength_score for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_evaluate_returns_hindi_prediction(self) -> None:
        chart = ChartSnapshot.from_rows([
            {"planet_name": "Sun",     "house": 1, "sign": "Aries", "degree": 10.0},
            {"planet_name": "Mercury", "house": 1, "sign": "Aries", "degree": 8.0},
        ])
        results = self.engine.evaluate(chart, language="hi", detected_only=True)
        budha = next((r for r in results if r.id == "budhaditya_yoga"), None)
        self.assertIsNotNone(budha)
        self.assertIn("\u092c\u0941\u0927\u093e\u0926\u093f\u0924\u094d\u092f", budha.prediction)

    def test_yoga_result_as_dict_is_json_serialisable(self) -> None:
        import json
        chart = ChartSnapshot.from_rows([
            {"planet_name": "Moon",    "house": 1, "sign": "Aries",  "degree": 5.0},
            {"planet_name": "Jupiter", "house": 4, "sign": "Cancer", "degree": 10.0},
        ])
        results = self.engine.evaluate(chart, detected_only=True)
        for r in results:
            serialised = json.dumps(r.as_dict())  # must not raise
            self.assertIn(r.id, serialised)

    def test_evaluate_include_trace_adds_trace_for_detected_yoga(self) -> None:
        chart = ChartSnapshot.from_rows([
            {"planet_name": "Sun",     "house": 1, "sign": "Aries", "degree": 10.0},
            {"planet_name": "Mercury", "house": 1, "sign": "Aries", "degree": 8.0},
        ])
        results = self.engine.evaluate(chart, detected_only=True, include_trace=True)
        budha = next((r for r in results if r.id == "budhaditya_yoga"), None)

        self.assertIsNotNone(budha)
        self.assertTrue(len(budha.trace) > 0)
        self.assertIsNotNone(budha.trace_summary)
        self.assertEqual(len(budha.trace), budha.trace_summary["total"])
        self.assertEqual(
            budha.trace_summary["total"],
            budha.trace_summary["passed"] + budha.trace_summary["failed"],
        )

    def test_evaluate_one_include_trace_returns_trace_for_non_detected_yoga(self) -> None:
        chart = ChartSnapshot.from_rows([
            {"planet_name": "Moon", "house": 1, "sign": "Aries", "degree": 5.0},
            {"planet_name": "Jupiter", "house": 3, "sign": "Gemini", "degree": 10.0},
        ])
        result = self.engine.evaluate_one("gajakesari_yoga", chart, include_trace=True)

        self.assertIsNotNone(result)
        self.assertFalse(result.detected)
        self.assertTrue(len(result.trace) > 0)
        self.assertIsNotNone(result.trace_summary)


if __name__ == "__main__":
    unittest.main()
