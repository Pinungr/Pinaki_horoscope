from __future__ import annotations

import unittest

from app.models.domain import ChartData
from core.engines.aspect_engine import calculate_aspects


class AspectEngineTests(unittest.TestCase):
    def test_calculate_aspects_returns_parashara_drishti_records(self) -> None:
        chart_data = [
            ChartData(user_id=1, planet_name="Saturn", sign="Gemini", house=3, degree=10.0),
            ChartData(user_id=1, planet_name="Moon", sign="Leo", house=5, degree=12.0),
            ChartData(user_id=1, planet_name="Jupiter", sign="Scorpio", house=9, degree=18.5),
            ChartData(user_id=1, planet_name="Mars", sign="Pisces", house=12, degree=2.3),
        ]

        aspects = calculate_aspects(chart_data)

        self.assertEqual(
            [
                {"from_planet": "Saturn", "to_planet": "Moon", "from_house": 3, "to_house": 5, "aspect_type": "drishti"},
                {"from_planet": "Saturn", "to_planet": "Jupiter", "from_house": 3, "to_house": 9, "aspect_type": "drishti"},
                {"from_planet": "Saturn", "to_planet": "Mars", "from_house": 3, "to_house": 12, "aspect_type": "drishti"},
                {"from_planet": "Jupiter", "to_planet": "Saturn", "from_house": 9, "to_house": 3, "aspect_type": "drishti"},
                {"from_planet": "Jupiter", "to_planet": "Moon", "from_house": 9, "to_house": 5, "aspect_type": "drishti"},
                {"from_planet": "Mars", "to_planet": "Saturn", "from_house": 12, "to_house": 3, "aspect_type": "drishti"},
            ],
            aspects,
        )

    def test_calculate_aspects_accepts_dictionary_entries_and_skips_non_planets(self) -> None:
        chart_data = [
            {"planet_name": "Sun", "house": 1},
            {"planet": "Moon", "house": 7},
            {"Planet": "Ascendant", "House": 7},
            {"planet_name": "Mars", "house": 8},
        ]

        aspects = calculate_aspects(chart_data)

        self.assertEqual(
            [
                {"from_planet": "Sun", "to_planet": "Moon", "from_house": 1, "to_house": 7, "aspect_type": "drishti"},
                {"from_planet": "Moon", "to_planet": "Sun", "from_house": 7, "to_house": 1, "aspect_type": "drishti"},
            ],
            aspects,
        )


if __name__ == "__main__":
    unittest.main()
