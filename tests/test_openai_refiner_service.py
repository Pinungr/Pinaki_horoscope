from __future__ import annotations

import unittest

from app.services.app_settings_service import AppSettingsService
from app.services.openai_refiner_service import OpenAIRefinerService


class _DisabledSettingsService(AppSettingsService):
    def load(self):  # type: ignore[override]
        return {
            "ai_enabled": False,
            "openai_api_key": "",
            "openai_model": "gpt-5-mini",
        }


class OpenAIRefinerServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = OpenAIRefinerService(_DisabledSettingsService())

    def test_refine_predictions_adds_refined_text_with_fallback_when_ai_is_disabled(self) -> None:
        predictions = [
            {
                "yoga": "Raj Yoga",
                "area": "career",
                "strength": "strong",
                "score": 85,
                "text": "You will achieve success in your career.",
            }
        ]

        refined = self.service.refine_predictions(predictions, {"top_areas": ["career"]}, tone="professional")

        self.assertEqual(1, len(refined))
        self.assertIn("refined_text", refined[0])
        self.assertIn("this is because", refined[0]["refined_text"].lower())
        self.assertIn("this indicates", refined[0]["refined_text"].lower())
        self.assertIn("you may experience", refined[0]["refined_text"].lower())

    def test_refine_predictions_supports_tone_parameter(self) -> None:
        predictions = [
            {
                "yoga": "Raj Yoga",
                "area": "career",
                "strength": "medium",
                "score": 70,
                "text": "You will progress in your work life.",
            }
        ]

        friendly = self.service.refine_predictions(predictions, {}, tone="friendly")[0]["refined_text"].lower()
        spiritual = self.service.refine_predictions(predictions, {}, tone="spiritual")[0]["refined_text"].lower()

        self.assertIn("supportive", friendly)
        self.assertIn("karmic", spiritual)


if __name__ == "__main__":
    unittest.main()

