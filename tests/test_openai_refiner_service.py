from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services.app_settings_service import AppSettingsService
from app.services.openai_refiner_service import OpenAIRefinerService


class _DisabledSettingsService(AppSettingsService):
    def load(self):  # type: ignore[override]
        return {
            "ai_enabled": False,
            "openai_api_key": "",
            "openai_model": "gpt-5-mini",
        }


class _EnabledSettingsService(AppSettingsService):
    def load(self):  # type: ignore[override]
        return {
            "ai_enabled": True,
            "openai_api_key": "test-key",
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

    def test_refine_predictions_includes_timing_hint_when_present(self) -> None:
        predictions = [
            {
                "yoga": "Gajakesari Yoga",
                "area": "career",
                "strength": "strong",
                "score": 90,
                "text": "You achieve success in career.",
                "timing": {"mahadasha": "Jupiter", "antardasha": "Moon", "relevance": "high"},
            }
        ]

        refined = self.service.refine_predictions(predictions, {}, tone="professional")

        self.assertEqual(1, len(refined))
        self.assertIn("mahadasha", refined[0]["refined_text"].lower())

    def test_refine_predictions_appends_timing_hint_in_ai_path(self) -> None:
        service = OpenAIRefinerService(_EnabledSettingsService())
        predictions = [
            {
                "yoga": "Gajakesari Yoga",
                "area": "career",
                "strength": "strong",
                "score": 90,
                "text": "You achieve success in career.",
                "timing": {"mahadasha": "Jupiter", "antardasha": "Moon", "relevance": "high"},
            }
        ]

        with patch.object(service, "_refine_prediction_text_with_ai", return_value="Career growth is visible."):
            refined = service.refine_predictions(predictions, {}, tone="professional")

        self.assertEqual(1, len(refined))
        self.assertIn("mahadasha", refined[0]["refined_text"].lower())

    def test_refine_predictions_respects_selected_language_for_fallback(self) -> None:
        predictions = [
            {
                "yoga": "Raj Yoga",
                "area": "career",
                "strength": "strong",
                "score": 85,
                "text": "करियर में सफलता के संकेत हैं।",
            }
        ]

        refined = self.service.refine_predictions(predictions, {"top_areas": ["career"]}, tone="professional", language="hi")

        self.assertEqual(1, len(refined))
        self.assertIn("ऐसा इसलिए", refined[0]["refined_text"])


if __name__ == "__main__":
    unittest.main()
