from __future__ import annotations

import unittest

from app.services.reasoning_service import ReasoningService, generate_prediction_explanation


class ReasoningServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ReasoningService()
        self.predictions = [
            {
                "yoga": "Raj Yoga",
                "area": "career",
                "strength": "strong",
                "score": 92,
                "timing": {
                    "mahadasha": "Jupiter",
                    "antardasha": "Venus",
                    "relevance": "high",
                    "matched_planets": ["jupiter"],
                },
            },
            {
                "yoga": "Dhana Yoga",
                "area": "wealth",
                "strength": "medium",
                "score": 74,
                "timing": {
                    "mahadasha": "Saturn",
                    "antardasha": "Mercury",
                    "relevance": "medium",
                    "matched_planets": ["mercury"],
                },
            },
        ]

    def test_generate_explanations_returns_structured_reasoning_rows(self) -> None:
        rows = self.service.generate_explanations(self.predictions)

        self.assertEqual(2, len(rows))
        self.assertEqual("career", rows[0]["area"])
        self.assertIn("Raj Yoga", rows[0]["explanation"])
        self.assertTrue(isinstance(rows[0]["supporting_factors"], list))
        self.assertTrue(any("Raj Yoga detected" == factor for factor in rows[0]["supporting_factors"]))
        self.assertTrue(any("Jupiter Mahadasha active" == factor for factor in rows[0]["supporting_factors"]))

    def test_generate_explanations_filters_by_user_question_area(self) -> None:
        rows = self.service.generate_explanations(self.predictions, user_question="How is my career?")

        self.assertEqual(1, len(rows))
        self.assertEqual("career", rows[0]["area"])

    def test_generate_explanations_maps_wealth_to_finance_when_filtered(self) -> None:
        rows = self.service.generate_explanations(self.predictions, user_question="How are my finances?")

        self.assertEqual(1, len(rows))
        self.assertEqual("finance", rows[0]["area"])
        self.assertIn("Dhana Yoga", rows[0]["explanation"])

    def test_generate_prediction_explanation_function_returns_single_row_shape(self) -> None:
        row = generate_prediction_explanation(self.predictions[0])

        self.assertIn("area", row)
        self.assertIn("explanation", row)
        self.assertIn("supporting_factors", row)


if __name__ == "__main__":
    unittest.main()

