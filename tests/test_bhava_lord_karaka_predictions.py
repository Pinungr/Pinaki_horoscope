from __future__ import annotations

import unittest

from core.predictions.prediction_service import PredictionService


class BhavaLordKarakaPredictionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = PredictionService()

    @staticmethod
    def _find_area(rows: list[dict], area: str) -> dict:
        for row in rows:
            if str(row.get("category", "")).strip().lower() == area:
                return row
        raise AssertionError(f"Area prediction '{area}' missing")

    def test_career_area_positive_when_lord_and_karaka_are_strong(self) -> None:
        chart = [
            {"planet_name": "Ascendant", "sign": "Aries", "house": 1, "degree": 0.0},
            {"planet_name": "Sun", "sign": "Leo", "house": 5, "degree": 10.0, "absolute_longitude": 130.0},
            {"planet_name": "Moon", "sign": "Taurus", "house": 2, "degree": 12.0, "absolute_longitude": 42.0},
            {"planet_name": "Saturn", "sign": "Libra", "house": 7, "degree": 14.0, "absolute_longitude": 194.0},
            {"planet_name": "Jupiter", "sign": "Cancer", "house": 4, "degree": 6.0, "absolute_longitude": 96.0},
        ]

        rows = self.service.build_bhava_lord_karaka_predictions(chart)
        career = self._find_area(rows, "career")

        self.assertEqual("positive", career["effect"])
        self.assertIn("10th lord", career["text"].lower())
        self.assertIn("karaka condition", career["text"].lower())
        self.assertTrue(any("area framework" in line.lower() for line in career["trace"]))

    def test_marriage_area_negative_when_lord_is_debilitated_and_afflicted(self) -> None:
        chart = [
            {"planet_name": "Ascendant", "sign": "Aries", "house": 1, "degree": 0.0, "absolute_longitude": 0.0},
            {"planet_name": "Sun", "sign": "Virgo", "house": 6, "degree": 10.0, "absolute_longitude": 160.0},
            {"planet_name": "Venus", "sign": "Virgo", "house": 6, "degree": 12.0, "absolute_longitude": 162.0},
            {"planet_name": "Mars", "sign": "Aries", "house": 1, "degree": 8.0, "absolute_longitude": 8.0},
            {"planet_name": "Jupiter", "sign": "Capricorn", "house": 10, "degree": 6.0, "absolute_longitude": 276.0},
        ]

        rows = self.service.build_bhava_lord_karaka_predictions(chart)
        marriage = self._find_area(rows, "marriage")

        self.assertEqual("negative", marriage["effect"])
        self.assertIn("7th lord", marriage["text"].lower())
        self.assertIn("debilitated", marriage["text"].lower())
        self.assertIn("karaka condition", marriage["text"].lower())

    def test_same_planetary_layout_changes_reasoning_when_lagna_changes(self) -> None:
        shared_planets = [
            {"planet_name": "Sun", "sign": "Leo", "house": 11, "degree": 8.0, "absolute_longitude": 128.0},
            {"planet_name": "Moon", "sign": "Scorpio", "house": 2, "degree": 5.0, "absolute_longitude": 215.0},
            {"planet_name": "Mars", "sign": "Capricorn", "house": 10, "degree": 16.0, "absolute_longitude": 286.0},
            {"planet_name": "Saturn", "sign": "Capricorn", "house": 10, "degree": 20.0, "absolute_longitude": 290.0},
            {"planet_name": "Jupiter", "sign": "Cancer", "house": 4, "degree": 5.0, "absolute_longitude": 95.0},
        ]

        aries_chart = [{"planet_name": "Ascendant", "sign": "Aries", "house": 1, "degree": 0.0}] + shared_planets
        libra_chart = [{"planet_name": "Ascendant", "sign": "Libra", "house": 1, "degree": 0.0}] + shared_planets

        aries_rows = self.service.build_bhava_lord_karaka_predictions(aries_chart)
        libra_rows = self.service.build_bhava_lord_karaka_predictions(libra_chart)
        aries_career = self._find_area(aries_rows, "career")
        libra_career = self._find_area(libra_rows, "career")

        self.assertNotEqual(aries_career["text"], libra_career["text"])
        self.assertIn("10th lord", aries_career["text"].lower())
        self.assertIn("10th lord", libra_career["text"].lower())


if __name__ == "__main__":
    unittest.main()
