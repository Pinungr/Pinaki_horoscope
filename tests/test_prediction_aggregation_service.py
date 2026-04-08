from __future__ import annotations

import unittest
from unittest.mock import patch

from core.predictions.aggregation_service import aggregate_predictions


class PredictionAggregationServiceTests(unittest.TestCase):
    def test_aggregate_predictions_returns_summary_and_details(self) -> None:
        aggregated = aggregate_predictions(["gajakesari_yoga"], "en")

        self.assertIn("gajakesari yoga", aggregated["summary"].lower())
        self.assertEqual(
            [
                {
                    "rule": "gajakesari_yoga",
                    "text": "Gajakesari Yoga is present: Moon and Jupiter combine in a kendra, supporting wisdom, recognition, and emotional strength.",
                    "explanation": "Due to Gajakesari Yoga.",
                }
            ],
            aggregated["details"],
        )

    def test_aggregate_predictions_deduplicates_repeated_rule_keys(self) -> None:
        aggregated = aggregate_predictions(["gajakesari_yoga", "gajakesari_yoga"], "en")

        self.assertEqual(1, len(aggregated["details"]))
        self.assertEqual(
            "Gajakesari Yoga is present: Moon and Jupiter combine in a kendra, supporting wisdom, recognition, and emotional strength.",
            aggregated["summary"],
        )

    def test_aggregate_predictions_falls_back_to_english_for_unknown_language(self) -> None:
        aggregated = aggregate_predictions(["gajakesari_yoga"], "fr")

        self.assertEqual(
            "Gajakesari Yoga is present: Moon and Jupiter combine in a kendra, supporting wisdom, recognition, and emotional strength.",
            aggregated["summary"],
        )

    def test_aggregate_predictions_sorts_rules_by_weight_before_building_output(self) -> None:
        with patch(
            "core.predictions.aggregation_service.get_prediction",
            side_effect=lambda key, _: f"text_{key}",
        ), patch(
            "core.predictions.aggregation_service.get_prediction_weight",
            side_effect=lambda key: {"rule_low": 1.0, "rule_high": 9.0}.get(key, 0.0),
        ):
            aggregated = aggregate_predictions(["rule_low", "rule_high"], "en")

        self.assertEqual("rule_high", aggregated["details"][0]["rule"])
        self.assertEqual("rule_low", aggregated["details"][1]["rule"])


if __name__ == "__main__":
    unittest.main()
