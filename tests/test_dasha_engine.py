from __future__ import annotations

from datetime import datetime
import unittest

from app.engine.dasha import DashaEngine


class DashaEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = DashaEngine()

    def test_calculate_dasha_returns_nine_sequential_periods(self) -> None:
        timeline = self.engine.calculate_dasha(120.0, "1995-08-17")

        self.assertEqual(9, len(timeline))
        self.assertEqual("1995-08-17", timeline[0]["start"])

        previous_end = None
        for period in timeline:
            start = datetime.strptime(period["start"], "%Y-%m-%d")
            end = datetime.strptime(period["end"], "%Y-%m-%d")
            self.assertLessEqual(start, end)
            if previous_end is not None:
                self.assertEqual(previous_end.strftime("%Y-%m-%d"), period["start"])
            previous_end = end

    def test_calculate_dasha_normalizes_out_of_range_longitude(self) -> None:
        wrapped_positive = self.engine.calculate_dasha(725.0, "2000-01-01")
        wrapped_negative = self.engine.calculate_dasha(5.0, "2000-01-01")

        self.assertEqual(
            [period["planet"] for period in wrapped_negative],
            [period["planet"] for period in wrapped_positive],
        )

    def test_calculate_dasha_falls_back_when_dob_is_invalid(self) -> None:
        timeline = self.engine.calculate_dasha(42.0, "invalid-date")

        self.assertEqual(9, len(timeline))
        self.assertIn("planet", timeline[0])
        self.assertIn("start", timeline[0])
        self.assertIn("end", timeline[0])


if __name__ == "__main__":
    unittest.main()
