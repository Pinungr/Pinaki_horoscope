from __future__ import annotations

import unittest

from app.services.event_service import EventService


class EventServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = EventService()
        self.timeline_data = {
            "timeline": [
                {
                    "period": "2026–2028",
                    "area": "career",
                    "event": "Career growth and recognition",
                    "confidence": 88,
                    "start": "2026-01-01",
                    "end": "2028-01-01",
                },
                {
                    "period": "2029–2030",
                    "area": "career",
                    "event": "Career role expansion",
                    "confidence": 84,
                    "start": "2029-01-01",
                    "end": "2030-01-01",
                },
                {
                    "period": "2027–2029",
                    "area": "finance",
                    "event": "Wealth growth and financial gains",
                    "confidence": 86,
                    "start": "2027-01-01",
                    "end": "2029-01-01",
                },
            ]
        }
        self.reasoning = [
            {"area": "career", "explanation": "Career is supported by Raj Yoga.", "supporting_factors": []},
            {"area": "finance", "explanation": "Finance is supported by Dhana Yoga.", "supporting_factors": []},
        ]

    def test_detect_intent_supports_required_domains(self) -> None:
        self.assertEqual("career", self.service.detect_intent("Will my career improve?"))
        self.assertEqual("marriage", self.service.detect_intent("When will I get married?"))
        self.assertEqual("finance", self.service.detect_intent("When will I earn money?"))
        self.assertEqual("health", self.service.detect_intent("How will my health be?"))
        self.assertEqual("general", self.service.detect_intent("Tell me something"))

    def test_filter_events_by_area_and_pick_top_events(self) -> None:
        career_events = self.service.filter_events_by_area(self.timeline_data["timeline"], "career")
        self.assertEqual(2, len(career_events))

        top = self.service.pick_top_events(career_events, max_events=1)
        self.assertEqual(1, len(top))
        self.assertEqual("Career growth and recognition", top[0]["event"])

    def test_predict_event_returns_answer_payload(self) -> None:
        payload = self.service.predict_event(
            user_query="Will my career improve?",
            predictions=[],
            timeline_data=self.timeline_data,
            reasoning_data=self.reasoning,
        )

        self.assertIn("answer", payload)
        self.assertIn("between", payload["answer"].lower())
        self.assertEqual("career", payload["intent"])
        self.assertGreater(payload["confidence"], 0)
        self.assertGreaterEqual(len(payload["supporting_events"]), 1)
        self.assertEqual("career", payload["reasoning"][0]["area"])

    def test_predict_event_returns_empty_for_general_query(self) -> None:
        payload = self.service.predict_event(
            user_query="Tell me about life.",
            predictions=[],
            timeline_data=self.timeline_data,
            reasoning_data=self.reasoning,
        )
        self.assertEqual("", payload["answer"])
        self.assertEqual(0, payload["confidence"])

    def test_predict_event_localizes_answer_for_selected_language(self) -> None:
        payload = self.service.predict_event(
            user_query="Will my career improve?",
            predictions=[],
            timeline_data=self.timeline_data,
            reasoning_data=self.reasoning,
            language="hi",
        )
        self.assertIn("संभावना", payload["answer"])


if __name__ == "__main__":
    unittest.main()
