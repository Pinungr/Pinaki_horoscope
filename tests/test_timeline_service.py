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
                "final_narrative": (
                    "Promise: Career outcomes are indicated through Raj Yoga. "
                    "Strength: strong bala. "
                    "Timing: Jupiter-Venus is active. "
                    "Caution: monitor lower-priority conflicts."
                ),
                "timing": {
                    "mahadasha": "Jupiter",
                    "antardasha": "Venus",
                    "relevance": "high",
                    "activation_level": "high",
                    "activation_score": 86,
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
                    "activation_level": "medium",
                    "activation_score": 58,
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
        self.assertIn("2025", rows[0]["period"])
        self.assertIn("2028", rows[0]["period"])
        self.assertEqual("Career growth and recognition", rows[0]["event"])
        self.assertGreaterEqual(rows[0]["confidence"], 90)
        self.assertIn("Raj Yoga", rows[0]["reasoning_link"])
        self.assertIn("Jupiter Mahadasha", rows[0]["reasoning_link"])
        self.assertEqual("active_now", rows[0]["activation_label"])
        self.assertIn("source_factors", rows[0])
        self.assertTrue(rows[0]["source_factors"])
        self.assertIn("prediction", rows[0])
        self.assertTrue(rows[0]["prediction"].startswith("Promise:"))

    def test_build_timeline_forecast_marks_future_supported_window_as_upcoming(self) -> None:
        forecast = self.service.build_timeline_forecast(self.predictions, self.dasha_timeline)
        rows = forecast["timeline"]

        finance_row = next(row for row in rows if row["area"] == "finance")
        self.assertEqual("upcoming", finance_row["activation_label"])
        self.assertGreaterEqual(finance_row["activation_score"], 40)
        self.assertTrue(
            any(
                "starting soon" in factor.lower() or "future" in factor.lower()
                for factor in finance_row["source_factors"]
            )
        )

    def test_build_timeline_forecast_marks_low_activation_as_dormant(self) -> None:
        dormant_prediction = [
            {
                "yoga": "Slow Yoga",
                "area": "career",
                "strength": "weak",
                "score": 40,
                "timing": {
                    "mahadasha": "Jupiter",
                    "antardasha": "Venus",
                    "relevance": "low",
                    "activation_level": "low",
                    "activation_score": 15,
                },
            }
        ]

        forecast = self.service.build_timeline_forecast(dormant_prediction, self.dasha_timeline)
        self.assertTrue(forecast["timeline"])
        self.assertEqual("dormant", forecast["timeline"][0]["activation_label"])
        self.assertTrue(forecast["timeline"][0]["source_factors"])

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

    def test_build_timeline_forecast_localizes_event_and_reasoning_text(self) -> None:
        forecast = self.service.build_timeline_forecast(
            self.predictions,
            self.dasha_timeline,
            language="hi",
        )

        self.assertTrue(forecast["timeline"])
        self.assertIn("करियर", forecast["timeline"][0]["event"])
        self.assertIn("महादशा", forecast["timeline"][0]["reasoning_link"])

    def test_compute_activation_trend_context_detects_falling_transition(self) -> None:
        prediction = {
            "yoga": "Raj Yoga",
            "area": "career",
            "strength": "strong",
            "score": 90,
            "timing": {
                "mahadasha": "Jupiter",
                "antardasha": "Venus",
                "activation_score": 84,
            },
        }
        windows = [
            {
                "mahadasha": "Jupiter",
                "antardasha": "Venus",
                "start": self.service._parse_iso_date("2026-01-01"),
                "end": self.service._parse_iso_date("2026-12-31"),
            },
            {
                "mahadasha": "Saturn",
                "antardasha": "Mercury",
                "start": self.service._parse_iso_date("2027-01-01"),
                "end": self.service._parse_iso_date("2027-12-31"),
            },
        ]

        trend = self.service._compute_activation_trend_context(
            prediction,
            windows,  # type: ignore[arg-type]
            today=self.service._parse_iso_date("2026-04-01"),
        )
        self.assertEqual("falling", trend["trend"])

    def test_source_factors_include_overlapping_influence_hint(self) -> None:
        forecast = self.service.build_timeline_forecast(self.predictions, self.dasha_timeline)
        row = forecast["timeline"][0]

        self.assertTrue(any("both support" in factor.lower() for factor in row["source_factors"]))


if __name__ == "__main__":
    unittest.main()
