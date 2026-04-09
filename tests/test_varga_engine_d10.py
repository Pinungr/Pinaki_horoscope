from __future__ import annotations

import unittest

from app.engine.varga_engine import VargaEngine
from app.models.domain import ChartData


class VargaEngineD10Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = VargaEngine()

    def test_get_d10_chart_returns_structured_payload(self) -> None:
        chart_data = [
            ChartData(user_id=1, planet_name="Ascendant", sign="Aries", house=1, degree=0.0),
            ChartData(user_id=1, planet_name="Sun", sign="Leo", house=5, degree=12.0),
            ChartData(user_id=1, planet_name="Saturn", sign="Capricorn", house=10, degree=10.0),
        ]

        d10 = self.engine.get_d10_chart(chart_data)

        self.assertIn("ascendant_sign", d10)
        self.assertIn("rows", d10)
        self.assertIn("placements", d10)
        self.assertTrue(d10["ascendant_sign"])
        self.assertIn("saturn", d10["placements"])
        self.assertIn("house", d10["placements"]["saturn"])
        self.assertGreaterEqual(d10["placements"]["saturn"]["house"], 1)
        self.assertLessEqual(d10["placements"]["saturn"]["house"], 12)

    def test_calculate_varga_chart_keeps_zero_degree_rows(self) -> None:
        chart_data = [
            ChartData(user_id=1, planet_name="Ascendant", sign="Aries", house=1, degree=0.0),
            {"planet_name": "Moon", "sign": "Taurus", "house": 2, "degree": 0.0},
        ]

        d10 = self.engine.calculate_varga_chart(10, chart_data)
        d60 = self.engine.calculate_varga_chart(60, chart_data)

        self.assertIn("Ascendant", d10)
        self.assertIn("Moon", d10)
        self.assertIn("Ascendant", d60)
        self.assertIn("Moon", d60)


if __name__ == "__main__":
    unittest.main()
