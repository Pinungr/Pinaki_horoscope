from __future__ import annotations

import unittest

from app.models.domain import ChartData
from core.utils.chart_utils import get_planet_data, get_planet_house


class _PlanetObject:
    def __init__(self, house: int, sign: str = "") -> None:
        self.house = house
        self.sign = sign


class _ChartObject:
    def __init__(self) -> None:
        self.moon = _PlanetObject(4, "Cancer")


class ChartUtilsTests(unittest.TestCase):
    def test_get_planet_house_supports_planet_mapping_shape(self) -> None:
        chart_data = {
            "sun": {"house": 1, "sign": "Aries"},
            "moon": {"house": 4, "sign": "Cancer"},
        }

        self.assertEqual(4, get_planet_house(chart_data, "Moon"))

    def test_get_planet_house_supports_object_based_fallback(self) -> None:
        chart_data = _ChartObject()

        self.assertEqual(4, get_planet_house(chart_data, "moon"))

    def test_get_planet_data_supports_iterable_row_input(self) -> None:
        chart_data = [
            ChartData(user_id=1, planet_name="Jupiter", sign="Cancer", house=10, degree=12.0),
        ]

        data = get_planet_data(chart_data, "jupiter")

        self.assertIsNotNone(data)
        assert data is not None
        self.assertEqual(10, data["house"])
        self.assertEqual("Cancer", data["sign"])


if __name__ == "__main__":
    unittest.main()

