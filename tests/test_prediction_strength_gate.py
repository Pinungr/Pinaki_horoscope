from __future__ import annotations

import unittest

from app.engine.prediction_scorer import (
    compose_temporal_score,
    compute_final_prediction,
    get_varga_concordance,
    rank_predictions_deterministically,
    score_predictions,
)


def _strength_payload(*, sun_total: float, moon_total: float) -> dict:
    return {
        "sun": {"planet": "sun", "total": sun_total},
        "moon": {"planet": "moon", "total": moon_total},
    }


class PredictionStrengthGateTests(unittest.TestCase):
    def test_compose_temporal_score_uses_base_dasha_transit_formula(self) -> None:
        payload = compose_temporal_score(60, 1.2, 1.1)

        self.assertEqual(60.0, payload["base_score"])
        self.assertEqual(1.2, payload["dasha_activation"])
        self.assertEqual(1.1, payload["transit_modifier"])
        self.assertEqual(79, payload["final_score"])

    def test_compose_temporal_score_limits_amplification_for_weak_promise(self) -> None:
        payload = compose_temporal_score(20, 1.4, 1.35)

        # Even with strong timing multipliers, weak natal promise remains bounded.
        self.assertLessEqual(payload["final_score"], 30)
        self.assertTrue(payload["cap_applied"])

    def test_compose_temporal_score_applies_varga_concordance_multiplier(self) -> None:
        payload = compose_temporal_score(40, 1.1, 1.0, 1.12)

        self.assertEqual(1.12, payload["varga_concordance"])
        self.assertEqual(49, payload["final_score"])

    def test_get_varga_concordance_high_when_all_layers_align(self) -> None:
        payload = get_varga_concordance(
            {
                "area": "career",
                "d1_signal": "support",
                "d9_signal": "support",
                "d10_signal": "confirm",
            }
        )

        self.assertGreaterEqual(payload["concordance_score"], 0.75)
        self.assertEqual("high", payload["agreement_level"])
        self.assertGreater(payload["concordance_modifier"], 1.0)

    def test_get_varga_concordance_medium_when_partial_agreement(self) -> None:
        payload = get_varga_concordance(
            {
                "area": "career",
                "d1_signal": "support",
                "d9_signal": "neutral",
                "d10_signal": "neutral",
            }
        )

        self.assertGreaterEqual(payload["concordance_score"], 0.4)
        self.assertLess(payload["concordance_score"], 0.75)
        self.assertEqual("medium", payload["agreement_level"])

    def test_get_varga_concordance_low_when_layers_conflict(self) -> None:
        payload = get_varga_concordance(
            {
                "area": "career",
                "d1_signal": "support",
                "d9_signal": "conflict",
                "d10_signal": "conflict",
            }
        )

        self.assertLess(payload["concordance_score"], 0.4)
        self.assertEqual("low", payload["agreement_level"])
        self.assertLess(payload["concordance_modifier"], 1.0)

    def test_get_varga_concordance_uses_neutral_fallback_when_missing_inputs(self) -> None:
        payload = get_varga_concordance({})

        self.assertEqual(0.5, payload["concordance_score"])
        self.assertEqual("medium", payload["agreement_level"])
        self.assertAlmostEqual(0.994, payload["concordance_modifier"], places=3)

    def test_compute_final_prediction_is_deterministic_and_trace_complete(self) -> None:
        context = {
            "prediction": "Career growth is indicated.",
            "base_strength": 72.0,
            "functional_weight": 1.15,
            "lordship_score": 68.0,
            "yoga_score": 80.0,
            "dasha_activation": 1.12,
            "transit_modifier": 1.04,
            "varga_concordance": 1.08,
        }

        first = compute_final_prediction(context)
        second = compute_final_prediction(context)

        self.assertEqual(first, second)
        self.assertIn("trace", first)
        self.assertIn("strength", first["trace"])
        self.assertIn("functional_nature", first["trace"])
        self.assertIn("lordship", first["trace"])
        self.assertIn("yoga", first["trace"])
        self.assertIn("dasha", first["trace"])
        self.assertIn("transit", first["trace"])
        self.assertIn("varga", first["trace"])

    def test_compute_final_prediction_handles_missing_layers_with_fallbacks(self) -> None:
        payload = compute_final_prediction({"prediction": "Fallback case", "base_strength": 60})

        self.assertGreaterEqual(payload["final_score"], 0)
        self.assertIn("trace", payload)
        self.assertIn("functional_nature", payload["trace"])
        self.assertIn("lordship", payload["trace"])

    def test_compute_final_prediction_dedupes_full_and_partial_signal_overlap(self) -> None:
        overlapping = compute_final_prediction(
            {
                "prediction": "Career rise",
                "base_strength": 82.0,
                "functional_weight": 1.18,
                "lordship_score": 78.0,
                "yoga_score": 84.0,
                "dasha_activation": 1.18,
                "transit_modifier": 1.12,
                "varga_concordance": 1.1,
                "signal_layers": {
                    "strength": [{"planet": "saturn", "house": 10, "concept_type": "strength"}],
                    "functional_nature": [{"planet": "saturn", "house": 10, "concept_type": "functional_nature"}],
                    "lordship": [
                        {"planet": "saturn", "house": 10, "concept_type": "lordship"},
                        {"planet": "saturn", "house": 10, "concept_type": "lordship"},
                    ],
                    "yoga": [{"planet": "saturn", "house": 10, "concept_type": "yoga"}],
                    "dasha": [{"planet": "saturn", "house": 10, "concept_type": "dasha"}],
                    "transit": [{"planet": "saturn", "house": 10, "concept_type": "transit"}],
                    "varga": [{"planet": "saturn", "house": 10, "concept_type": "varga"}],
                },
            }
        )
        independent = compute_final_prediction(
            {
                "prediction": "Career rise",
                "base_strength": 82.0,
                "functional_weight": 1.18,
                "lordship_score": 78.0,
                "yoga_score": 84.0,
                "dasha_activation": 1.18,
                "transit_modifier": 1.12,
                "varga_concordance": 1.1,
                "signal_layers": {
                    "strength": [{"planet": "sun", "house": 1, "concept_type": "strength"}],
                    "functional_nature": [{"planet": "moon", "house": 2, "concept_type": "functional_nature"}],
                    "lordship": [{"planet": "mars", "house": 3, "concept_type": "lordship"}],
                    "yoga": [{"planet": "jupiter", "house": 4, "concept_type": "yoga"}],
                    "dasha": [{"planet": "venus", "house": 5, "concept_type": "dasha"}],
                    "transit": [{"planet": "saturn", "house": 6, "concept_type": "transit"}],
                    "varga": [{"planet": "mercury", "house": 7, "concept_type": "varga"}],
                },
            }
        )

        self.assertLess(overlapping["final_score"], independent["final_score"])
        dedupe_summary = overlapping["trace"]["deduplication"]["summary"]
        self.assertTrue(any("counted once" in str(line).lower() for line in dedupe_summary))
        self.assertTrue(any("reduced" in str(line).lower() for line in dedupe_summary))

    def test_compute_final_prediction_keeps_independent_signals_unsuppressed(self) -> None:
        payload = compute_final_prediction(
            {
                "prediction": "Independent signals",
                "base_strength": 70.0,
                "functional_weight": 1.1,
                "lordship_score": 68.0,
                "yoga_score": 72.0,
                "dasha_activation": 1.08,
                "transit_modifier": 1.06,
                "varga_concordance": 1.02,
                "signal_layers": {
                    "strength": [{"planet": "sun", "house": 1, "concept_type": "strength"}],
                    "functional_nature": [{"planet": "moon", "house": 2, "concept_type": "functional_nature"}],
                    "lordship": [{"planet": "mars", "house": 3, "concept_type": "lordship"}],
                    "yoga": [{"planet": "jupiter", "house": 4, "concept_type": "yoga"}],
                    "dasha": [{"planet": "venus", "house": 5, "concept_type": "dasha"}],
                    "transit": [{"planet": "saturn", "house": 6, "concept_type": "transit"}],
                    "varga": [{"planet": "mercury", "house": 7, "concept_type": "varga"}],
                },
            }
        )

        layers = payload["trace"]["deduplication"]["layers"]
        for layer_name in ("strength", "functional_nature", "lordship", "yoga", "dasha", "transit", "varga"):
            self.assertEqual(1.0, layers[layer_name]["dedupe_factor"])
            self.assertFalse(layers[layer_name]["suppression_applied"])

    def test_compute_final_prediction_partial_overlap_uses_diminishing_sequence(self) -> None:
        payload = compute_final_prediction(
            {
                "prediction": "Partial overlap",
                "base_strength": 75.0,
                "functional_weight": 1.16,
                "lordship_score": 74.0,
                "yoga_score": 80.0,
                "dasha_activation": 1.12,
                "transit_modifier": 1.1,
                "varga_concordance": 1.05,
                "signal_layers": {
                    "strength": [{"planet": "saturn", "house": 10, "concept_type": "strength"}],
                    "functional_nature": [{"planet": "saturn", "house": 10, "concept_type": "functional_nature"}],
                    "lordship": [{"planet": "saturn", "house": 10, "concept_type": "lordship"}],
                    "yoga": [{"planet": "jupiter", "house": 4, "concept_type": "yoga"}],
                },
            }
        )

        layers = payload["trace"]["deduplication"]["layers"]
        self.assertEqual(1.0, layers["strength"]["dedupe_factor"])
        self.assertEqual(0.5, layers["functional_nature"]["dedupe_factor"])
        self.assertEqual(0.25, layers["lordship"]["dedupe_factor"])
        self.assertEqual(1.0, layers["yoga"]["dedupe_factor"])

    def test_rank_predictions_deterministically_breaks_ties_consistently(self) -> None:
        rows = [
            {"yoga": "Beta Yoga", "area": "career", "score": 80, "text": "B", "prediction": "B"},
            {"yoga": "Alpha Yoga", "area": "career", "score": 80, "text": "A", "prediction": "A"},
            {"yoga": "Gamma Yoga", "area": "health", "score": 75, "text": "C", "prediction": "C"},
        ]

        ranked_one = rank_predictions_deterministically(rows)
        ranked_two = rank_predictions_deterministically(list(reversed(rows)))

        self.assertEqual(
            [row["yoga"] for row in ranked_one],
            [row["yoga"] for row in ranked_two],
        )
        self.assertEqual(["Alpha Yoga", "Beta Yoga", "Gamma Yoga"], [row["yoga"] for row in ranked_one])
        self.assertEqual([1, 2, 3], [row["rank"] for row in ranked_one])

    def test_rank_predictions_adds_parashari_narrative_sections_in_order(self) -> None:
        ranked = rank_predictions_deterministically(
            [
                {
                    "yoga": "Raj Yoga",
                    "area": "career",
                    "score": 89,
                    "final_score": 89,
                    "text": "Career rise is indicated.",
                    "prediction": "Career rise is indicated.",
                    "state": "strong",
                    "strength": "strong",
                    "strength_score": 82.0,
                    "lordship_score": 74.0,
                    "yoga_score": 85.0,
                    "dasha_activation": 1.18,
                    "timing": {
                        "mahadasha": "Jupiter",
                        "antardasha": "Venus",
                        "activation_level": "high",
                        "relevance": "high",
                    },
                    "agreement_level": "high",
                    "concordance_score": 0.84,
                    "transit": {"support_state": "amplifying", "trigger_level": "high"},
                    "karaka_source": "supportive",
                }
            ]
        )

        row = ranked[0]
        self.assertTrue(row["promise_text"].startswith("Promise:"))
        self.assertTrue(row["strength_text"].startswith("Strength:"))
        self.assertTrue(row["timing_text"].startswith("Timing:"))
        self.assertTrue(row["caution_text"].startswith("Caution:"))
        final_narrative = row["final_narrative"]
        self.assertLess(final_narrative.index("Promise:"), final_narrative.index("Strength:"))
        self.assertLess(final_narrative.index("Strength:"), final_narrative.index("Timing:"))
        self.assertLess(final_narrative.index("Timing:"), final_narrative.index("Caution:"))

    def test_conflict_case_strong_yoga_but_no_dasha_is_suppressed(self) -> None:
        ranked = rank_predictions_deterministically(
            [
                {
                    "yoga": "Gajakesari Yoga",
                    "area": "career",
                    "score": 86,
                    "final_score": 86,
                    "text": "Career rise is indicated.",
                    "prediction": "Career rise is indicated.",
                    "state": "strong",
                    "strength_score": 80.0,
                    "lordship_score": 74.0,
                    "yoga_score": 88.0,
                    "dasha_activation": 0.9,
                    "timing": {"activation_level": "low", "relevance": "low"},
                    "agreement_level": "high",
                    "concordance_score": 0.82,
                    "transit": {"support_state": "amplifying", "trigger_level": "high"},
                }
            ]
        )

        row = ranked[0]
        self.assertEqual("suppressed", row["dominant_outcome"])
        self.assertEqual("", row["final_prediction"])
        self.assertEqual(0, row["final_score"])
        self.assertIn("dasha", row["resolution_explanation"].lower())
        self.assertTrue(row["caution_text"].startswith("Caution:"))
        self.assertIn("suppressed", row["caution_text"].lower())

    def test_conflict_case_weak_natal_strong_transit_still_suppressed(self) -> None:
        ranked = rank_predictions_deterministically(
            [
                {
                    "yoga": "Career Yoga",
                    "area": "career",
                    "score": 78,
                    "final_score": 78,
                    "text": "Career uplift indicated.",
                    "prediction": "Career uplift indicated.",
                    "state": "strong",
                    "strength_score": 28.0,
                    "lordship_score": 72.0,
                    "yoga_score": 80.0,
                    "dasha_activation": 1.25,
                    "timing": {"activation_level": "high", "relevance": "high"},
                    "agreement_level": "high",
                    "concordance_score": 0.78,
                    "transit": {"support_state": "amplifying", "trigger_level": "high"},
                }
            ]
        )

        row = ranked[0]
        self.assertEqual("suppressed", row["dominant_outcome"])
        self.assertEqual(0, row["final_score"])
        self.assertTrue(any(item["factor"] == "transit_trigger" for item in row["suppressed_signals"]))

    def test_conflict_case_strong_natal_conflicting_varga_reduces_confidence(self) -> None:
        ranked = rank_predictions_deterministically(
            [
                {
                    "yoga": "Career Yoga",
                    "area": "career",
                    "score": 82,
                    "final_score": 82,
                    "text": "Career progress indicated.",
                    "prediction": "Career progress indicated.",
                    "state": "strong",
                    "strength_score": 80.0,
                    "lordship_score": 76.0,
                    "yoga_score": 84.0,
                    "dasha_activation": 1.18,
                    "timing": {"activation_level": "high", "relevance": "high"},
                    "agreement_level": "low",
                    "concordance_score": 0.21,
                    "transit": {"support_state": "neutral", "trigger_level": "medium"},
                }
            ]
        )

        row = ranked[0]
        self.assertIn(row["dominant_outcome"], {"valid", "tempered"})
        self.assertGreater(row["final_score"], 0)
        self.assertLess(row["resolved_confidence_multiplier"], 1.0)
        self.assertTrue(any(item["factor"] == "varga_concordance" for item in row["suppressed_signals"]))

    def test_conflict_case_multiple_conflicts_follow_priority(self) -> None:
        ranked = rank_predictions_deterministically(
            [
                {
                    "yoga": "Mixed Career Yoga",
                    "area": "career",
                    "score": 79,
                    "final_score": 79,
                    "text": "Career promise exists.",
                    "prediction": "Career promise exists.",
                    "state": "strong",
                    "strength_score": 82.0,
                    "lordship_score": 34.0,
                    "yoga_score": 86.0,
                    "dasha_activation": 1.2,
                    "timing": {"activation_level": "high", "relevance": "high"},
                    "agreement_level": "high",
                    "concordance_score": 0.84,
                    "transit": {"support_state": "amplifying", "trigger_level": "high"},
                }
            ]
        )

        row = ranked[0]
        self.assertEqual("tempered", row["dominant_outcome"])
        self.assertIn("house-lord", row["dominant_reasoning"].lower())
        self.assertTrue(any(item["factor"] == "yoga_status" for item in row["suppressed_signals"]))

    def test_weak_chart_blocks_high_confidence_outcome(self) -> None:
        predictions = [
            {
                "text": "Career growth is strongly indicated.",
                "category": "career",
                "weight": 2.4,
                "effect": "positive",
                "result_key": "career_growth_strong",
                "rule_confidence": "high",
            }
        ]

        scored = score_predictions(
            predictions,
            strength_payload=_strength_payload(sun_total=120.0, moon_total=110.0),
        )

        career = scored["career"]
        self.assertNotEqual("high", career["confidence"])
        self.assertEqual("downgraded", career["strength_gate"]["status"])
        self.assertIn("strength gate lowered confidence", career["summary"].lower())

    def test_strong_chart_allows_high_confidence_outcome(self) -> None:
        predictions = [
            {
                "text": "Career growth is strongly indicated.",
                "category": "career",
                "weight": 2.4,
                "effect": "positive",
                "result_key": "career_growth_strong",
                "rule_confidence": "high",
            }
        ]

        scored = score_predictions(
            predictions,
            strength_payload=_strength_payload(sun_total=390.0, moon_total=360.0),
        )

        career = scored["career"]
        self.assertEqual("high", career["confidence"])
        self.assertEqual("passed", career["strength_gate"]["status"])

    def test_borderline_chart_downgrades_to_medium(self) -> None:
        predictions = [
            {
                "text": "Financial gains are strongly indicated.",
                "category": "finance",
                "weight": 2.1,
                "effect": "positive",
                "result_key": "finance_gain_strong",
                "rule_confidence": "high",
            }
        ]

        scored = score_predictions(
            predictions,
            strength_payload=_strength_payload(sun_total=286.0, moon_total=264.0),
        )

        finance = scored["finance"]
        self.assertEqual("medium", finance["confidence"])
        self.assertEqual("downgraded", finance["strength_gate"]["status"])

    def test_rare_yoga_override_allows_high_confidence_on_low_strength(self) -> None:
        predictions = [
            {
                "text": "Hamsa Yoga gives strong support and rise in status.",
                "category": "yoga",
                "weight": 2.3,
                "effect": "positive",
                "result_key": "hamsa_yoga",
                "rule_confidence": "high",
            }
        ]

        scored = score_predictions(
            predictions,
            strength_payload=_strength_payload(sun_total=120.0, moon_total=100.0),
        )

        yoga = scored["yoga"]
        self.assertEqual("high", yoga["confidence"])
        self.assertTrue(yoga["strength_gate"]["override_applied"])
        self.assertIn("rare_yoga", yoga["strength_gate"]["override_reasons"])
        self.assertEqual("override", yoga["strength_gate"]["status"])


if __name__ == "__main__":
    unittest.main()
