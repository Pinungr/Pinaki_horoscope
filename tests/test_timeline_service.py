from __future__ import annotations

import unittest

from app.services.timeline_service import TimelineService


class TimelineServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = TimelineService()
        self.predictions = [
            {
                "yoga": "Raj Yoga",
                "area": "career",
                "strength": "strong",
                "score": 92,
                "text": "You will achieve authority and success in career.",
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
                "score": 76,
                "text": "Financial momentum improves.",
                "timing": {
                    "mahadasha": "Saturn",
                    "antardasha": "Mercury",
                    "relevance": "medium",
                    "matched_planets": ["mercury"],
                },
            },
        ]
        self.dasha_timeline = [
            {
                "planet": "Jupiter",
                "start": "2024-01-01",
                "end": "2040-01-01",
                "sub_periods": [
                    {"planet": "Sun", "start": "2024-01-01", "end": "2025-06-01"},
                    {"planet": "Venus", "start": "2025-06-02", "end": "2028-03-01"},
                ],
            },
            {
                "planet": "Saturn",
                "start": "2040-01-02",
                "end": "2059-01-01",
                "sub_periods": [
                    {"planet": "Mercury", "start": "2042-01-01", "end": "2044-01-01"},
                ],
            },
        ]

    def test_extract_dasha_windows_supports_sub_period_expansion(self) -> None:
        windows = self.service.extract_dasha_windows(self.dasha_timeline)

        self.assertEqual(3, len(windows))
        self.assertEqual("Jupiter", windows[0]["mahadasha"])
        self.assertEqual("Sun", windows[0]["antardasha"])
        self.assertEqual("Venus", windows[1]["antardasha"])

    def test_build_timeline_forecast_maps_predictions_to_dasha_windows(self) -> None:
        forecast = self.service.build_timeline_forecast(self.predictions, self.dasha_timeline)
        rows = forecast["timeline"]

        self.assertEqual(2, len(rows))
        self.assertEqual("career", rows[0]["area"])
        self.assertEqual("2025–2028", rows[0]["period"])
        self.assertEqual("Career growth and recognition", rows[0]["event"])
        self.assertGreaterEqual(rows[0]["confidence"], 90)
        self.assertIn("Raj Yoga", rows[0]["reasoning_link"])
        self.assertIn("Jupiter Mahadasha", rows[0]["reasoning_link"])

    def test_build_timeline_forecast_supports_month_granularity(self) -> None:
        forecast = self.service.build_timeline_forecast(
            self.predictions,
            self.dasha_timeline,
            month_granularity=True,
        )

        self.assertTrue(any("Jun 2025" in row["period"] for row in forecast["timeline"]))

    def test_build_timeline_forecast_returns_empty_when_no_windows_match(self) -> None:
        unmatched = [
            {
                "yoga": "Chandra Yoga",
                "area": "home",
                "strength": "strong",
                "score": 80,
                "timing": {"mahadasha": "Moon", "antardasha": "Moon", "relevance": "high"},
            }
        ]

        forecast = self.service.build_timeline_forecast(unmatched, self.dasha_timeline)
        self.assertEqual([], forecast["timeline"])


if __name__ == "__main__":
    unittest.main()

