from __future__ import annotations

from unittest.mock import patch
import unittest

from app.services.horoscope_chat_service import HoroscopeChatService


class _StubHoroscopeService:
    def load_chart_for_user(self, _user_id: int):
        return [], {
            "career": {"summary": "Career growth is indicated.", "confidence": "high", "score": 85},
            "finance": {"summary": "Financial progress is indicated.", "confidence": "medium", "score": 70},
        }

    def get_timeline_data(self, _user_id: int):
        return {"timeline": [], "prediction_scores": {}}


class HoroscopeChatServiceReasoningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.chat_service = HoroscopeChatService(horoscope_service=_StubHoroscopeService())
        self.unified_predictions = [
            {
                "yoga": "Raj Yoga",
                "area": "career",
                "strength": "strong",
                "score": 92,
                "final_narrative": (
                    "Promise: Career outcomes are indicated through Raj Yoga. "
                    "Strength: strong bala and supportive varga. "
                    "Timing: Jupiter-Venus window is active. "
                    "Caution: monitor lower-priority conflicting signals."
                ),
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
                "score": 73,
                "final_narrative": (
                    "Promise: Wealth outcomes are indicated through Dhana Yoga. "
                    "Strength: steady bala with medium concordance. "
                    "Timing: Saturn-Mercury support is emerging. "
                    "Caution: outcomes remain gradual."
                ),
                "timing": {
                    "mahadasha": "Saturn",
                    "antardasha": "Mercury",
                    "relevance": "medium",
                    "matched_planets": ["mercury"],
                },
            },
        ]

    def test_analyze_query_attaches_filtered_reasoning(self) -> None:
        dasha = [
            {
                "planet": "Jupiter",
                "start": "2025-01-01",
                "end": "2035-01-01",
                "sub_periods": [
                    {"planet": "Venus", "start": "2026-01-01", "end": "2028-01-01"},
                ],
            }
        ]
        with patch.object(self.chat_service, "_get_unified_predictions", return_value=self.unified_predictions), patch.object(
            self.chat_service,
            "_get_unified_dasha_timeline",
            return_value=dasha,
        ):
            result = self.chat_service.analyze_query("How is my career?", user_id=1)

        reasoning_rows = result["data"]["reasoning"]
        self.assertEqual(1, len(reasoning_rows))
        self.assertEqual("career", reasoning_rows[0]["area"])
        self.assertEqual(1, len(result["data"]["timeline_forecast"]["timeline"]))
        self.assertTrue(result["data"]["prediction_summary"].startswith("Promise:"))

    def test_ask_uses_event_service_for_specific_query(self) -> None:
        dasha = [
            {
                "planet": "Jupiter",
                "start": "2025-01-01",
                "end": "2035-01-01",
                "sub_periods": [
                    {"planet": "Venus", "start": "2026-01-01", "end": "2028-01-01"},
                ],
            }
        ]
        with patch.object(self.chat_service, "_get_unified_predictions", return_value=self.unified_predictions), patch.object(
            self.chat_service,
            "_get_unified_dasha_timeline",
            return_value=dasha,
        ):
            result = self.chat_service.ask(1, "How is my career?")

        self.assertEqual("event_service", result["response_source"])
        self.assertIn("between", result["response"].lower())
        self.assertIn("event_prediction", result)

    def test_ask_falls_back_to_local_response_for_general_query(self) -> None:
        with patch.object(self.chat_service, "_get_unified_predictions", return_value=self.unified_predictions), patch.object(
            self.chat_service,
            "_get_unified_dasha_timeline",
            return_value=[],
        ):
            result = self.chat_service.ask(1, "Tell me about my life")

        self.assertEqual("local", result["response_source"])
        self.assertIn("why:", result["response"].lower())

    def test_follow_up_why_reuses_previous_intent_context(self) -> None:
        with patch.object(self.chat_service, "_get_unified_predictions", return_value=self.unified_predictions), patch.object(
            self.chat_service,
            "_get_unified_dasha_timeline",
            return_value=[],
        ):
            self.chat_service.ask(1, "How is my career?")
            follow_up = self.chat_service.ask(1, "Why?")

        self.assertEqual("career", follow_up["intent"])
        self.assertIn("earlier career question", follow_up["response"].lower())


if __name__ == "__main__":
    unittest.main()
