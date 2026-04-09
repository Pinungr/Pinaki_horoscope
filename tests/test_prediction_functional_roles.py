from __future__ import annotations

import unittest

from app.engine.prediction_scorer import score_predictions


def _strong_strength_payload() -> dict:
    return {
        "sun": {"planet": "sun", "total": 390.0},
        "moon": {"planet": "moon", "total": 360.0},
    }


def _weak_strength_payload() -> dict:
    return {
        "sun": {"planet": "sun", "total": 120.0},
        "moon": {"planet": "moon", "total": 100.0},
    }


class PredictionFunctionalRoleTests(unittest.TestCase):
    def test_benefic_role_boosts_positive_outcome(self) -> None:
        scored = score_predictions(
            [
                {
                    "text": "Career growth is indicated.",
                    "category": "career",
                    "effect": "positive",
                    "weight": 1.0,
                    "functional_lagna": "aries",
                    "functional_roles": [{"planet": "jupiter", "role": "benefic"}],
                }
            ],
            strength_payload=_strong_strength_payload(),
        )

        career = scored["career"]
        self.assertGreater(career["positive_score"], 1.0)
        self.assertIn("functional benefic", career["summary"].lower())
        self.assertTrue(any("functional role impact" in row.lower() for row in career["trace"]))

    def test_malefic_role_can_invert_positive_effect(self) -> None:
        scored = score_predictions(
            [
                {
                    "text": "Status rise is indicated.",
                    "category": "career",
                    "effect": "positive",
                    "weight": 1.2,
                    "functional_lagna": "libra",
                    "functional_roles": [{"planet": "mars", "role": "malefic"}],
                }
            ],
            strength_payload=_strong_strength_payload(),
        )

        career = scored["career"]
        self.assertEqual("negative", career["effect"])
        self.assertLess(career["score"], 0.0)
        self.assertIn("functional malefic", career["summary"].lower())

    def test_yogakaraka_role_amplifies_positive_confidence(self) -> None:
        scored = score_predictions(
            [
                {
                    "text": "Career rise is strongly indicated.",
                    "category": "career",
                    "effect": "positive",
                    "weight": 1.4,
                    "functional_lagna": "libra",
                    "functional_roles": [{"planet": "saturn", "role": "yogakaraka"}],
                }
            ],
            strength_payload=_strong_strength_payload(),
        )

        career = scored["career"]
        self.assertEqual("positive", career["effect"])
        self.assertGreater(career["score"], 2.0)
        self.assertEqual("high", career["confidence"])
        self.assertIn("functional yogakaraka", career["summary"].lower())

    def test_functional_role_impact_applies_before_strength_gate(self) -> None:
        scored = score_predictions(
            [
                {
                    "text": "Career rise is strongly indicated.",
                    "category": "career",
                    "effect": "positive",
                    "weight": 1.4,
                    "functional_lagna": "libra",
                    "functional_roles": [{"planet": "saturn", "role": "yogakaraka"}],
                }
            ],
            strength_payload=_weak_strength_payload(),
        )

        career = scored["career"]
        self.assertEqual("downgraded", career["strength_gate"]["status"])
        self.assertNotEqual("high", career["confidence"])
        self.assertIn("functional yogakaraka", career["summary"].lower())
        self.assertIn("strength gate lowered confidence", career["summary"].lower())


if __name__ == "__main__":
    unittest.main()
