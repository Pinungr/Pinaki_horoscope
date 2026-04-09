from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

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

    @staticmethod
    def _build_engine_with_two_conjunction_yogas() -> UnifiedAstrologyEngine:
        gajakesari = YogaDefinition.from_dict(
            {
                "id": "gajakesari_yoga",
                "conditions": [{"type": "conjunction", "planets": ["moon", "jupiter"]}],
                "prediction": {"en": "placeholder"},
            }
        )
        chandra_shukra = YogaDefinition.from_dict(
            {
                "id": "chandra_shukra_yoga",
                "conditions": [{"type": "conjunction", "planets": ["moon", "venus"]}],
                "prediction": {"en": "placeholder"},
            }
        )
        yoga_engine = YogaEngine(
            config_dir=Path("/nonexistent"),
            extra_definitions=[gajakesari, chandra_shukra],
        )
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
        self.assertIn("functional_nature", result)
        self.assertIn("house_lord_details", result)
        self.assertIn("confidence_score", result)

        self.assertEqual(1, len(result["yogas"]))
        self.assertEqual("gajakesari_yoga", result["yogas"][0]["id"])
        self.assertEqual(9, len(result["dasha"]["timeline"]))
        self.assertEqual(1, len(result["final_predictions"]))
        self.assertEqual("gajakesari_yoga", result["final_predictions"][0]["rule"])
        self.assertEqual("aries", result["functional_nature"]["lagna"])
        self.assertEqual("malefic", result["functional_nature"]["roles"]["saturn"])
        self.assertEqual("moon", result["house_lord_details"][4]["lord"])
        self.assertGreaterEqual(result["confidence_score"], 0)
        self.assertLessEqual(result["confidence_score"], 100)

    def test_analyze_exposes_dual_reference_transits(self) -> None:
        engine = self._build_engine_with_single_gajakesari()
        chart_data = [
            {"planet_name": "Ascendant", "sign": "Aries", "house": 1, "degree": 5.0},
            {"planet_name": "Moon", "sign": "Cancer", "house": 4, "degree": 10.0},
            {"planet_name": "Jupiter", "sign": "Cancer", "house": 4, "degree": 12.0},
        ]
        transit_stub = {
            "reference": "both",
            "target_time": "2026-04-09T00:00:00",
            "transits": {"saturn": {"house_from_reference": 8, "sign": "aquarius"}},
            "from_lagna": {"saturn": {"house_from_reference": 11, "sign": "aquarius"}},
            "from_moon": {"saturn": {"house_from_reference": 8, "sign": "aquarius"}},
            "transit_matrix": {
                "saturn": {
                    "transit_planet": "saturn",
                    "from_lagna": {
                        "house_position": 11,
                        "effects": ["Supportive"],
                        "strength_modifiers": ["supportive_house_context"],
                    },
                    "from_moon": {
                        "house_position": 8,
                        "effects": ["Demanding"],
                        "strength_modifiers": ["challenging_house_context"],
                    },
                }
            },
        }

        with patch.object(engine.transit_engine, "calculate_transits", return_value=transit_stub):
            result = engine.analyze(chart_data, dob="1990-01-01", language="en")

        self.assertIn("transits", result)
        self.assertEqual("both", result["transits"]["reference"])
        self.assertIn("from_lagna", result["transits"])
        self.assertIn("from_moon", result["transits"])
        self.assertIn("transit_matrix", result["transits"])
        self.assertIn("interpretations_by_reference", result["transits"])
        self.assertIn("from_lagna", result["transits"]["interpretations_by_reference"])
        self.assertIn("from_moon", result["transits"]["interpretations_by_reference"])

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
        self.assertIn("functional_nature", result)
        self.assertIn("house_lord_details", result)
        self.assertEqual(1, result["meta"]["total_yogas"])
        self.assertEqual(1, len(result["predictions"]))
        self.assertEqual("aries", result["functional_nature"]["lagna"])
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

    def test_generate_full_analysis_respects_selected_language_for_prediction_text(self) -> None:
        engine = self._build_engine_with_single_gajakesari()
        chart_data = [
            {"planet_name": "Moon", "sign": "Cancer", "house": 4, "degree": 10.0},
            {"planet_name": "Jupiter", "sign": "Cancer", "house": 4, "degree": 12.0},
        ]

        result = engine.generate_full_analysis(chart_data, language="hi")

        self.assertEqual(1, len(result["predictions"]))
        self.assertIn("उपस्थित", result["predictions"][0]["text"])


    def test_generate_full_analysis_does_not_create_prediction_from_transit_only(self) -> None:
        engine = self._build_engine_with_single_gajakesari()
        chart_data = [
            {"planet_name": "Moon", "sign": "Aries", "house": 1, "degree": 10.0},
            {"planet_name": "Jupiter", "sign": "Taurus", "house": 2, "degree": 12.0},
        ]
        strong_transit = {
            "reference": "both",
            "from_lagna": {"jupiter": {"house_from_reference": 10}},
            "from_moon": {"jupiter": {"house_from_reference": 10}},
            "transit_matrix": {
                "jupiter": {
                    "transit_planet": "jupiter",
                    "from_lagna": {"house_position": 10},
                    "from_moon": {"house_position": 10},
                }
            },
        }

        with patch.object(engine.transit_engine, "calculate_transits", return_value=strong_transit):
            result = engine.generate_full_analysis(chart_data, dob="1990-01-01", language="en")

        self.assertEqual([], result["predictions"])

    def test_generate_full_analysis_strong_natal_weak_transit_results_in_moderated_score(self) -> None:
        engine = self._build_engine_with_single_gajakesari()
        chart_data = [
            {"planet_name": "Moon", "sign": "Cancer", "house": 4, "degree": 10.0},
            {"planet_name": "Jupiter", "sign": "Cancer", "house": 4, "degree": 12.0},
        ]
        dasha_stub = {
            "mahadasha": "Jupiter",
            "antardasha": "Moon",
            "relevance": "high",
            "activation_level": "high",
            "activation_score": 84.0,
            "matched_planets": ["jupiter", "moon"],
            "score_multiplier": 1.25,
            "dasha_evidence": ["Current Mahadasha lord Jupiter supports this promise."],
        }
        weak_transit_stub = {
            "score_multiplier": 0.7,
            "trigger_level": "low",
            "trigger_now": False,
            "support_state": "suppressing",
            "matched_planets": ["saturn"],
            "source_factors": ["Transit of Saturn through challenging houses is suppressing immediate manifestation."],
            "dominant_trigger": {"planet": "saturn", "house": 8, "reference": "lagna", "strength": 0.2},
        }

        with patch.object(engine.prediction_service, "evaluate_dasha_relevance", return_value=dasha_stub), patch.object(
            engine.prediction_service, "evaluate_transit_trigger", return_value=weak_transit_stub
        ):
            result = engine.generate_full_analysis(chart_data, dob="1990-01-01", language="en")

        self.assertEqual(1, len(result["predictions"]))
        row = result["predictions"][0]
        self.assertEqual("suppressing", row["transit"]["support_state"])
        self.assertLess(row["score"], 85)
        self.assertIn("activation_trace", row)
        self.assertTrue(any("transit" in str(line).lower() for line in row["activation_trace"]))

    def test_generate_full_analysis_strong_natal_dasha_transit_amplifies_score(self) -> None:
        engine = self._build_engine_with_single_gajakesari()
        chart_data = [
            {"planet_name": "Moon", "sign": "Cancer", "house": 4, "degree": 10.0},
            {"planet_name": "Jupiter", "sign": "Cancer", "house": 4, "degree": 12.0},
        ]
        dasha_stub = {
            "mahadasha": "Jupiter",
            "antardasha": "Moon",
            "relevance": "high",
            "activation_level": "high",
            "activation_score": 90.0,
            "matched_planets": ["jupiter", "moon"],
            "score_multiplier": 1.3,
            "dasha_evidence": ["Current Mahadasha lord Jupiter supports this promise."],
        }
        strong_transit_stub = {
            "score_multiplier": 1.24,
            "trigger_level": "high",
            "trigger_now": True,
            "support_state": "amplifying",
            "matched_planets": ["jupiter"],
            "source_factors": ["Transit of Jupiter is over house 10 from Lagna, matching current dasha lord."],
            "dominant_trigger": {"planet": "jupiter", "house": 10, "reference": "lagna", "strength": 0.44},
        }

        with patch.object(engine.prediction_service, "evaluate_dasha_relevance", return_value=dasha_stub), patch.object(
            engine.prediction_service, "evaluate_transit_trigger", return_value=strong_transit_stub
        ):
            result = engine.generate_full_analysis(chart_data, dob="1990-01-01", language="en")

        self.assertEqual(1, len(result["predictions"]))
        row = result["predictions"][0]
        self.assertEqual("amplifying", row["transit"]["support_state"])
        self.assertGreater(row["dasha_activation"], 1.0)
        self.assertGreater(row["transit_modifier"], 1.0)
        self.assertTrue(any("transit of" in str(line).lower() for line in row["activation_trace"]))

    def test_generate_full_analysis_conflicting_dasha_and_transit_reduces_score(self) -> None:
        engine = self._build_engine_with_single_gajakesari()
        chart_data = [
            {"planet_name": "Moon", "sign": "Cancer", "house": 4, "degree": 10.0},
            {"planet_name": "Jupiter", "sign": "Cancer", "house": 4, "degree": 12.0},
        ]
        dasha_stub = {
            "mahadasha": "Jupiter",
            "antardasha": "Moon",
            "relevance": "high",
            "activation_level": "high",
            "activation_score": 88.0,
            "matched_planets": ["jupiter"],
            "score_multiplier": 1.25,
            "dasha_evidence": ["Current Mahadasha lord Jupiter supports this promise."],
        }
        neutral_transit_stub = {
            "score_multiplier": 1.0,
            "trigger_level": "medium",
            "trigger_now": False,
            "support_state": "neutral",
            "matched_planets": [],
            "source_factors": ["Current transits are neutral for this promise."],
            "dominant_trigger": None,
        }
        suppressing_transit_stub = {
            "score_multiplier": 0.72,
            "trigger_level": "low",
            "trigger_now": False,
            "support_state": "suppressing",
            "matched_planets": ["saturn"],
            "source_factors": ["Transit of Saturn through challenging houses is suppressing immediate manifestation."],
            "dominant_trigger": {"planet": "saturn", "house": 8, "reference": "lagna", "strength": 0.3},
        }

        with patch.object(engine.prediction_service, "evaluate_dasha_relevance", return_value=dasha_stub), patch.object(
            engine.prediction_service,
            "evaluate_transit_trigger",
            side_effect=[neutral_transit_stub, suppressing_transit_stub],
        ):
            baseline = engine.generate_full_analysis(chart_data, dob="1990-01-01", language="en")
            conflicting = engine.generate_full_analysis(chart_data, dob="1990-01-01", language="en")

        self.assertEqual(1, len(baseline["predictions"]))
        self.assertEqual(1, len(conflicting["predictions"]))
        baseline_row = baseline["predictions"][0]
        conflicting_row = conflicting["predictions"][0]
        self.assertGreater(
            baseline_row["transit_modifier"],
            conflicting_row["transit_modifier"],
        )
        if baseline_row["base_score"] > 0:
            self.assertGreater(
                baseline_row["score"],
                conflicting_row["score"],
            )
        self.assertEqual("suppressing", conflicting["predictions"][0]["transit"]["support_state"])

    def test_generate_full_analysis_exposes_varga_concordance_fields(self) -> None:
        engine = self._build_engine_with_single_gajakesari()
        chart_data = [
            {"planet_name": "Moon", "sign": "Cancer", "house": 4, "degree": 10.0},
            {"planet_name": "Jupiter", "sign": "Cancer", "house": 4, "degree": 12.0},
        ]
        dasha_stub = {
            "mahadasha": "Jupiter",
            "antardasha": "Moon",
            "relevance": "high",
            "activation_level": "high",
            "activation_score": 91.0,
            "matched_planets": ["jupiter", "moon"],
            "score_multiplier": 1.25,
            "d10_status": "confirm",
            "d10_evidence": ["D10 10th lord is well placed."],
            "dasha_evidence": ["Current Mahadasha lord Jupiter supports this promise."],
        }
        neutral_transit_stub = {
            "score_multiplier": 1.0,
            "trigger_level": "medium",
            "trigger_now": False,
            "support_state": "neutral",
            "matched_planets": [],
            "source_factors": ["Current transits are neutral for this promise."],
            "dominant_trigger": None,
        }
        navamsha_stub = {
            "moon": {"navamsha_sign": "taurus"},
            "jupiter": {"navamsha_sign": "cancer"},
        }

        with patch.object(engine.prediction_service, "evaluate_dasha_relevance", return_value=dasha_stub), patch.object(
            engine.prediction_service, "evaluate_transit_trigger", return_value=neutral_transit_stub
        ), patch.object(engine.navamsha_engine, "calculate_navamsha", return_value=navamsha_stub), patch.object(
            engine, "_evaluate_d1_signal", return_value=("support", 0.8, ["D1 strongly supports this promise."])
        ), patch.object(
            engine, "_evaluate_d9_signal", return_value=("support", 0.7, ["D9 strongly supports this promise."])
        ), patch.object(
            engine, "_evaluate_d10_signal", return_value=("support", 0.8, ["D10 confirms execution support."])
        ):
            result = engine.generate_full_analysis(chart_data, dob="1990-01-01", language="en")

        self.assertEqual(1, len(result["predictions"]))
        row = result["predictions"][0]
        self.assertIn("concordance_score", row)
        self.assertIn("agreement_level", row)
        self.assertIn("concordance_factors", row)
        self.assertGreaterEqual(row["concordance_score"], 0.75)
        self.assertEqual("high", row["agreement_level"])
        self.assertTrue(any("concordance" in str(line).lower() for line in row["activation_trace"]))

    def test_generate_full_analysis_low_concordance_reduces_final_score(self) -> None:
        engine = self._build_engine_with_single_gajakesari()
        chart_data = [
            {"planet_name": "Moon", "sign": "Cancer", "house": 4, "degree": 10.0},
            {"planet_name": "Jupiter", "sign": "Cancer", "house": 4, "degree": 12.0},
        ]
        neutral_transit_stub = {
            "score_multiplier": 1.0,
            "trigger_level": "medium",
            "trigger_now": False,
            "support_state": "neutral",
            "matched_planets": [],
            "source_factors": ["Current transits are neutral for this promise."],
            "dominant_trigger": None,
        }
        high_concordance_dasha = {
            "mahadasha": "Jupiter",
            "antardasha": "Moon",
            "relevance": "high",
            "activation_level": "high",
            "activation_score": 90.0,
            "matched_planets": ["jupiter", "moon"],
            "score_multiplier": 1.22,
            "d10_status": "confirm",
            "d10_evidence": ["D10 supports execution."],
            "dasha_evidence": ["Current Mahadasha lord Jupiter supports this promise."],
        }
        low_concordance_dasha = {
            **high_concordance_dasha,
            "d10_status": "conflict",
            "d10_evidence": ["D10 conflicts with this promise."],
        }
        high_navamsha = {
            "moon": {"navamsha_sign": "taurus"},
            "jupiter": {"navamsha_sign": "cancer"},
        }
        low_navamsha = {
            "moon": {"navamsha_sign": "scorpio"},
            "jupiter": {"navamsha_sign": "capricorn"},
        }

        with patch.object(
            engine.prediction_service,
            "evaluate_dasha_relevance",
            side_effect=[high_concordance_dasha, low_concordance_dasha],
        ), patch.object(
            engine.prediction_service,
            "evaluate_transit_trigger",
            return_value=neutral_transit_stub,
        ), patch.object(
            engine.navamsha_engine,
            "calculate_navamsha",
            side_effect=[high_navamsha, low_navamsha],
        ), patch.object(
            engine, "_evaluate_d1_signal", return_value=("support", 0.8, ["D1 strongly supports this promise."])
        ), patch.object(
            engine,
            "_evaluate_d9_signal",
            side_effect=[
                ("support", 0.7, ["D9 strongly supports this promise."]),
                ("conflict", -0.6, ["D9 weakens this promise."]),
            ],
        ), patch.object(
            engine,
            "_evaluate_d10_signal",
            side_effect=[
                ("support", 0.8, ["D10 confirms execution support."]),
                ("conflict", -0.8, ["D10 conflicts with execution support."]),
            ],
        ):
            high = engine.generate_full_analysis(chart_data, dob="1990-01-01", language="en")
            low = engine.generate_full_analysis(chart_data, dob="1990-01-01", language="en")

        self.assertEqual(1, len(high["predictions"]))
        self.assertEqual(1, len(low["predictions"]))
        high_row = high["predictions"][0]
        low_row = low["predictions"][0]
        self.assertGreater(high_row["concordance_score"], low_row["concordance_score"])
        self.assertGreater(high_row["varga_concordance"], low_row["varga_concordance"])
        if high_row["base_score"] > 0:
            self.assertGreater(high_row["score"], low_row["score"])

    def test_generate_full_analysis_is_deterministic_for_same_input(self) -> None:
        engine = self._build_engine_with_single_gajakesari()
        chart_data = [
            {"planet_name": "Ascendant", "sign": "Aries", "house": 1, "degree": 5.0},
            {"planet_name": "Moon", "sign": "Cancer", "house": 4, "degree": 10.0},
            {"planet_name": "Jupiter", "sign": "Cancer", "house": 4, "degree": 12.0},
        ]

        run_one = engine.generate_full_analysis(
            chart_data,
            dob="1990-01-01",
            language="en",
            transit_date="2026-04-09T00:00:00+00:00",
        )
        run_two = engine.generate_full_analysis(
            chart_data,
            dob="1990-01-01",
            language="en",
            transit_date="2026-04-09T00:00:00+00:00",
        )

        self.assertEqual(run_one["predictions"], run_two["predictions"])
        self.assertEqual(run_one["summary"], run_two["summary"])
        self.assertEqual(run_one["meta"]["generated_at"], run_two["meta"]["generated_at"])

    def test_generate_full_analysis_trace_contains_all_m_layers(self) -> None:
        engine = self._build_engine_with_single_gajakesari()
        chart_data = [
            {"planet_name": "Ascendant", "sign": "Aries", "house": 1, "degree": 5.0},
            {"planet_name": "Moon", "sign": "Cancer", "house": 4, "degree": 10.0},
            {"planet_name": "Jupiter", "sign": "Cancer", "house": 4, "degree": 12.0},
        ]

        result = engine.generate_full_analysis(
            chart_data,
            dob="1990-01-01",
            language="en",
            transit_date="2026-04-09T00:00:00+00:00",
        )

        self.assertEqual(1, len(result["predictions"]))
        row = result["predictions"][0]
        self.assertIn("trace", row)
        self.assertIn("strength", row["trace"])
        self.assertIn("functional_nature", row["trace"])
        self.assertIn("lordship", row["trace"])
        self.assertIn("yoga", row["trace"])
        self.assertIn("dasha", row["trace"])
        self.assertIn("transit", row["trace"])
        self.assertIn("varga", row["trace"])
        self.assertIn("deduplication", row["trace"])
        self.assertIn("summary", row["trace"]["deduplication"])
        self.assertTrue(any("dedup" in str(line).lower() or "overlap" in str(line).lower() for line in row["activation_trace"]))
        self.assertIn("final_prediction", row)
        self.assertIn("dominant_reasoning", row)
        self.assertIn("suppressed_signals", row)
        self.assertIn("resolution_explanation", row)
        self.assertIn("rank", row)

    def test_generate_full_analysis_ranking_is_stable_for_tied_scores(self) -> None:
        engine = self._build_engine_with_two_conjunction_yogas()
        chart_data = [
            {"planet_name": "Ascendant", "sign": "Aries", "house": 1, "degree": 5.0},
            {"planet_name": "Moon", "sign": "Cancer", "house": 4, "degree": 10.0},
            {"planet_name": "Jupiter", "sign": "Cancer", "house": 4, "degree": 12.0},
            {"planet_name": "Venus", "sign": "Cancer", "house": 4, "degree": 14.0},
        ]

        tied_score_payload = {
            "final_score": 71,
            "trace": {
                "strength": {},
                "functional_nature": {},
                "lordship": {},
                "yoga": {},
                "dasha": {},
                "transit": {},
                "varga": {},
            },
            "score_components": {
                "weighted_base_score": 65.0,
                "temporal": {
                    "dasha_activation": 1.0,
                    "transit_modifier": 1.0,
                    "varga_concordance": 1.0,
                },
            },
        }

        with patch("core.engines.astrology_engine.compute_final_prediction", return_value=tied_score_payload):
            first = engine.generate_full_analysis(chart_data, dob="1990-01-01", language="en")
            second = engine.generate_full_analysis(chart_data, dob="1990-01-01", language="en")

        self.assertEqual(
            [row["yoga"] for row in first["predictions"]],
            [row["yoga"] for row in second["predictions"]],
        )
        self.assertEqual(
            list(range(1, len(first["predictions"]) + 1)),
            [row["rank"] for row in first["predictions"]],
        )


if __name__ == "__main__":
    unittest.main()
