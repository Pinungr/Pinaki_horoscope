from __future__ import annotations

import unittest

from core.engines.strength_engine import PlanetStrength
from core.yoga.models import ChartSnapshot
from core.yoga.yoga_engine import YogaEngine


class _StubStrengthEngine:
    def __init__(self, score_map: dict[str, int] | None = None, sthana_map: dict[str, float] | None = None) -> None:
        self._scores = {str(key).strip().lower(): int(value) for key, value in (score_map or {}).items()}
        self._sthana = {str(key).strip().lower(): float(value) for key, value in (sthana_map or {}).items()}

    def _to_result(self, planet: str) -> PlanetStrength:
        normalized = str(planet).strip().lower()
        score = int(self._scores.get(normalized, 84))
        level = "strong" if score >= 70 else "medium" if score >= 40 else "weak"
        breakdown = {
            "sthana_bala": float(self._sthana.get(normalized, 56.0)),
            "total": 300.0,
        }
        return PlanetStrength(planet=normalized, score=score, level=level, breakdown=breakdown)

    def score_chart(self, chart: ChartSnapshot) -> dict[str, PlanetStrength]:
        planets = [planet for planet in chart.placements.keys() if planet not in {"ascendant", "lagna"}]
        return {planet: self._to_result(planet) for planet in planets}

    def score_planet(self, planet: str, _chart: ChartSnapshot) -> PlanetStrength:
        return self._to_result(planet)


class YogaBhangaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = YogaEngine(strength_engine=_StubStrengthEngine())

    def _assert_state(self, yoga_id: str, rows: list[dict], expected_state: str) -> None:
        result = self.engine.evaluate_one(yoga_id, ChartSnapshot.from_rows(rows))
        self.assertIsNotNone(result)
        self.assertTrue(result.detected)
        self.assertEqual(expected_state, result.state)

    def test_raja_yoga_9_10_states(self) -> None:
        strong_rows = [
            {"planet_name": "Ascendant", "house": 1, "sign": "Aries", "degree": 1.0},
            {"planet_name": "Mars", "house": 1, "sign": "Aries", "degree": 5.0},
            {"planet_name": "Jupiter", "house": 9, "sign": "Sagittarius", "degree": 12.0},
            {"planet_name": "Saturn", "house": 10, "sign": "Capricorn", "degree": 15.0},
            {"planet_name": "Sun", "house": 2, "sign": "Taurus", "degree": 3.0},
        ]
        weak_rows = [
            {"planet_name": "Ascendant", "house": 1, "sign": "Aries", "degree": 1.0},
            {"planet_name": "Mars", "house": 1, "sign": "Aries", "degree": 5.0},
            {"planet_name": "Jupiter", "house": 9, "sign": "Sagittarius", "degree": 12.0},
            {"planet_name": "Saturn", "house": 10, "sign": "Capricorn", "degree": 15.0},
            {"planet_name": "Sun", "house": 10, "sign": "Capricorn", "degree": 14.0},
        ]
        cancelled_rows = [
            {"planet_name": "Ascendant", "house": 1, "sign": "Aries", "degree": 1.0},
            {"planet_name": "Mars", "house": 1, "sign": "Aries", "degree": 5.0},
            {"planet_name": "Jupiter", "house": 9, "sign": "Sagittarius", "degree": 12.0},
            {"planet_name": "Saturn", "house": 1, "sign": "Aries", "degree": 6.0},
            {"planet_name": "Sun", "house": 2, "sign": "Taurus", "degree": 3.0},
        ]

        self._assert_state("raja_yoga_9_10", strong_rows, "strong")
        self._assert_state("raja_yoga_9_10", weak_rows, "weak")
        self._assert_state("raja_yoga_9_10", cancelled_rows, "cancelled")

    def test_dhana_yoga_states(self) -> None:
        strong_rows = [
            {"planet_name": "Ascendant", "house": 1, "sign": "Taurus", "degree": 1.0},
            {"planet_name": "Mercury", "house": 2, "sign": "Gemini", "degree": 12.0},
            {"planet_name": "Jupiter", "house": 11, "sign": "Pisces", "degree": 10.0},
            {"planet_name": "Sun", "house": 5, "sign": "Virgo", "degree": 2.0},
        ]
        weak_rows = [
            {"planet_name": "Ascendant", "house": 1, "sign": "Taurus", "degree": 1.0},
            {"planet_name": "Mercury", "house": 2, "sign": "Gemini", "degree": 12.0},
            {"planet_name": "Jupiter", "house": 11, "sign": "Pisces", "degree": 10.0},
            {"planet_name": "Sun", "house": 2, "sign": "Gemini", "degree": 10.0},
        ]
        cancelled_rows = [
            {"planet_name": "Ascendant", "house": 1, "sign": "Taurus", "degree": 1.0},
            {"planet_name": "Mercury", "house": 11, "sign": "Pisces", "degree": 12.0},
            {"planet_name": "Jupiter", "house": 9, "sign": "Capricorn", "degree": 10.0},
            {"planet_name": "Sun", "house": 5, "sign": "Virgo", "degree": 2.0},
        ]

        self._assert_state("dhana_yoga_2_11", strong_rows, "strong")
        self._assert_state("dhana_yoga_2_11", weak_rows, "weak")
        self._assert_state("dhana_yoga_2_11", cancelled_rows, "cancelled")

    def test_gajakesari_states(self) -> None:
        strong_rows = [
            {"planet_name": "Ascendant", "house": 1, "sign": "Aries", "degree": 1.0},
            {"planet_name": "Moon", "house": 1, "sign": "Aries", "degree": 9.0},
            {"planet_name": "Jupiter", "house": 4, "sign": "Cancer", "degree": 14.0},
            {"planet_name": "Sun", "house": 11, "sign": "Aquarius", "degree": 5.0},
        ]
        weak_rows = [
            {"planet_name": "Ascendant", "house": 1, "sign": "Aries", "degree": 1.0},
            {"planet_name": "Moon", "house": 1, "sign": "Aries", "degree": 9.0},
            {"planet_name": "Jupiter", "house": 4, "sign": "Cancer", "degree": 14.0},
            {"planet_name": "Sun", "house": 4, "sign": "Cancer", "degree": 13.0},
        ]
        cancelled_rows = [
            {"planet_name": "Ascendant", "house": 1, "sign": "Aries", "degree": 1.0},
            {"planet_name": "Moon", "house": 1, "sign": "Aries", "degree": 9.0},
            {"planet_name": "Jupiter", "house": 4, "sign": "Capricorn", "degree": 14.0},
            {"planet_name": "Sun", "house": 11, "sign": "Aquarius", "degree": 5.0},
        ]

        self._assert_state("gajakesari_yoga", strong_rows, "strong")
        self._assert_state("gajakesari_yoga", weak_rows, "weak")
        self._assert_state("gajakesari_yoga", cancelled_rows, "cancelled")

    def test_chandra_mangal_states(self) -> None:
        strong_rows = [
            {"planet_name": "Ascendant", "house": 1, "sign": "Aries", "degree": 1.0},
            {"planet_name": "Moon", "house": 2, "sign": "Taurus", "degree": 11.0},
            {"planet_name": "Mars", "house": 2, "sign": "Taurus", "degree": 13.0},
            {"planet_name": "Sun", "house": 10, "sign": "Capricorn", "degree": 6.0},
        ]
        weak_rows = [
            {"planet_name": "Ascendant", "house": 1, "sign": "Aries", "degree": 1.0},
            {"planet_name": "Moon", "house": 2, "sign": "Taurus", "degree": 11.0},
            {"planet_name": "Mars", "house": 2, "sign": "Taurus", "degree": 13.0},
            {"planet_name": "Sun", "house": 1, "sign": "Aries", "degree": 28.0},
        ]
        cancelled_rows = [
            {"planet_name": "Ascendant", "house": 1, "sign": "Aries", "degree": 1.0},
            {"planet_name": "Moon", "house": 8, "sign": "Scorpio", "degree": 11.0},
            {"planet_name": "Mars", "house": 8, "sign": "Scorpio", "degree": 13.0},
            {"planet_name": "Sun", "house": 1, "sign": "Aries", "degree": 6.0},
        ]

        self._assert_state("chandra_mangal_yoga", strong_rows, "strong")
        self._assert_state("chandra_mangal_yoga", weak_rows, "weak")
        self._assert_state("chandra_mangal_yoga", cancelled_rows, "cancelled")

    def test_neecha_bhanga_raja_yoga_states(self) -> None:
        strong_rows = [
            {"planet_name": "Ascendant", "house": 1, "sign": "Aries", "degree": 1.0},
            {"planet_name": "Saturn", "house": 10, "sign": "Capricorn", "degree": 15.0},
            {"planet_name": "Sun", "house": 7, "sign": "Libra", "degree": 5.0},
        ]
        weak_rows = [
            {"planet_name": "Ascendant", "house": 1, "sign": "Aries", "degree": 1.0},
            {"planet_name": "Saturn", "house": 10, "sign": "Capricorn", "degree": 15.0},
            {"planet_name": "Sun", "house": 9, "sign": "Capricorn", "degree": 0.0},
            {"planet_name": "Moon", "house": 8, "sign": "Scorpio", "degree": 9.0},
        ]
        cancelled_rows = [
            {"planet_name": "Ascendant", "house": 1, "sign": "Aries", "degree": 1.0},
            {"planet_name": "Saturn", "house": 10, "sign": "Capricorn", "degree": 15.0},
            {"planet_name": "Sun", "house": 6, "sign": "Virgo", "degree": 5.0},
            {"planet_name": "Moon", "house": 2, "sign": "Taurus", "degree": 9.0},
        ]

        self._assert_state("neecha_bhanga_raja_yoga", strong_rows, "strong")
        self._assert_state("neecha_bhanga_raja_yoga", weak_rows, "weak")
        self._assert_state("neecha_bhanga_raja_yoga", cancelled_rows, "cancelled")

    def test_partial_bhanga_downgrade_only(self) -> None:
        rows = [
            {"planet_name": "Ascendant", "house": 1, "sign": "Aries", "degree": 1.0},
            {"planet_name": "Moon", "house": 1, "sign": "Aries", "degree": 9.0},
            {"planet_name": "Jupiter", "house": 4, "sign": "Cancer", "degree": 14.0},
            {"planet_name": "Sun", "house": 4, "sign": "Cancer", "degree": 13.0},
        ]
        result = self.engine.evaluate_one("gajakesari_yoga", ChartSnapshot.from_rows(rows))
        self.assertIsNotNone(result)
        self.assertEqual("weak", result.state)
        self.assertIn("Bhanga downgraded yoga strength", " ".join(result.reasoning))

    def test_conflicting_strong_signals_and_affliction(self) -> None:
        rows = [
            {"planet_name": "Ascendant", "house": 1, "sign": "Aries", "degree": 1.0},
            {"planet_name": "Moon", "house": 2, "sign": "Taurus", "degree": 11.0},
            {"planet_name": "Mars", "house": 2, "sign": "Taurus", "degree": 13.0},
            {"planet_name": "Sun", "house": 1, "sign": "Aries", "degree": 28.0},
        ]
        result = self.engine.evaluate_one("chandra_mangal_yoga", ChartSnapshot.from_rows(rows))
        self.assertIsNotNone(result)
        self.assertEqual("weak", result.state)
        self.assertIn("Bhanga", " ".join(result.reasoning))


if __name__ == "__main__":
    unittest.main()
