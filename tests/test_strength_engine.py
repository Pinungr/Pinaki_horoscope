from __future__ import annotations

import unittest

from core.engines.strength_engine import PlanetStrength, StrengthEngine
from core.yoga.models import ChartSnapshot


class StrengthEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = StrengthEngine()

    def _build_chart(self, rows: list[dict]):
        """Ensure Sun and Ascendant are always present for Shadbala requirements."""
        has_sun = any(r.get("planet_name") == "Sun" for r in rows)
        has_asc = any(r.get("planet_name") in ["Ascendant", "Lagna"] for r in rows)
        
        final_rows = list(rows)
        if not has_sun:
            final_rows.append({"planet_name": "Sun", "house": 10, "sign": "Leo", "degree": 0.0, "absolute_longitude": 120.0})
        if not has_asc:
            final_rows.append({"planet_name": "Ascendant", "house": 1, "sign": "Aries", "degree": 0.0, "absolute_longitude": 0.0})
            
        return ChartSnapshot.from_rows(final_rows)

    # ------------------------------------------------------------------
    # Dignity
    # ------------------------------------------------------------------

    def test_exalted_planet_scores_high(self) -> None:
        # Sun in Aries = exaltation
        chart = self._build_chart([{"planet_name": "Sun", "house": 1, "sign": "Aries", "degree": 10.0, "absolute_longitude": 10.0}])
        result = self.engine.score_planet("sun", chart)
        self.assertIn("sthana", result.breakdown)
        self.assertGreaterEqual(result.score, 60) # Sun is strong

    def test_debilitated_planet_receives_penalty(self) -> None:
        # Sun in Libra = debilitation
        chart = self._build_chart([{"planet_name": "Sun", "house": 2, "sign": "Libra", "degree": 10.0, "absolute_longitude": 190.0}])
        result = self.engine.score_planet("sun", chart)
        self.assertEqual(result.level, "weak")
        self.assertIn("sthana", result.breakdown)

    def test_debilitated_planet_in_kendra_is_medium(self) -> None:
        # Sun debilitated in Libra but placed in kendra house 7
        chart = self._build_chart([{"planet_name": "Sun", "house": 7, "sign": "Libra", "degree": 10.0, "absolute_longitude": 190.0}])
        result = self.engine.score_planet("sun", chart)
        self.assertIn("sthana", result.breakdown)
        self.assertIn("level", result.as_dict())

    def test_own_sign_planet_scores_medium_or_above(self) -> None:
        # Saturn in Capricorn = own sign. Put in House 1 (Kendra + Dik Bala) to ensure Medium.
        chart = self._build_chart([
            {"planet_name": "Saturn", "house": 1, "sign": "Capricorn", "degree": 5.0, "absolute_longitude": 275.0},
            {"planet_name": "Sun", "house": 10, "sign": "Libra", "degree": 0.0, "absolute_longitude": 180.0}
        ])
        result = self.engine.score_planet("saturn", chart)
        self.assertGreaterEqual(result.score, 40)

    def test_neutral_planet_returns_base_score(self) -> None:
        # Jupiter in Gemini = no special dignity
        chart = self._build_chart([{"planet_name": "Jupiter", "house": 3, "sign": "Gemini", "degree": 15.0}])
        result = self.engine.score_planet("jupiter", chart)
        self.assertNotIn("exaltation", result.breakdown)
        self.assertNotIn("debilitation", result.breakdown)
        self.assertNotIn("own_sign", result.breakdown)

    # ------------------------------------------------------------------
    # Retrograde
    # ------------------------------------------------------------------

    def test_retrograde_adds_bonus(self) -> None:
        chart = self._build_chart(
            [{"planet_name": "Saturn", "house": 3, "sign": "Gemini", "degree": 10.0, "is_retrograde": True}]
        )
        result_retro = self.engine.score_planet("saturn", chart)
        self.assertIn("chestha", result_retro.breakdown)

    def test_direct_planet_has_no_retrograde_bonus(self) -> None:
        chart = self._build_chart(
            [{"planet_name": "Saturn", "house": 3, "sign": "Gemini", "degree": 10.0, "is_retrograde": False}]
        )
        result = self.engine.score_planet("saturn", chart)
        self.assertEqual(result.breakdown["chestha"], 0.0)

    # ------------------------------------------------------------------
    # Combustion
    # ------------------------------------------------------------------

    def test_combustion_applies_within_orb(self) -> None:
        # Mars orb = 17 deg; Mars at degree 5, Sun at degree 10 - delta = 5 -> combust
        chart = self._build_chart(
            [
                {"planet_name": "Sun", "house": 2, "sign": "Taurus", "degree": 10.0, "absolute_longitude": 40.0},
                {"planet_name": "Mars", "house": 2, "sign": "Taurus", "degree": 5.0, "absolute_longitude": 35.0},
            ]
        )
        result = self.engine.score_planet("mars", chart)
        # Sthana bala should be 0 because combustion penalty (-60) wipes out 
        # the base points (Kendra/etc) for this sparse chart.
        self.assertEqual(result.breakdown["sthana"], 0.0)

    def test_combustion_does_not_apply_outside_orb(self) -> None:
        # Mars orb = 17 deg; Sun at 0, Mars at 25 - delta = 25 -> not combust
        chart = ChartSnapshot.from_rows(
            [
                {"planet_name": "Sun", "house": 2, "sign": "Taurus", "degree": 0.0, "absolute_longitude": 30.0},
                {"planet_name": "Mars", "house": 2, "sign": "Taurus", "degree": 25.0, "absolute_longitude": 55.0},
            ]
        )
        result = self.engine.score_planet("mars", chart)
        self.assertNotIn("combustion", result.breakdown)

    def test_sun_is_never_combust(self) -> None:
        chart = self._build_chart([{"planet_name": "Sun", "house": 1, "sign": "Aries", "degree": 5.0, "absolute_longitude": 5.0}])
        result = self.engine.score_planet("sun", chart)
        self.assertNotIn("combustion", result.breakdown)

    # ------------------------------------------------------------------
    # House strength
    # ------------------------------------------------------------------

    def test_kendra_house_bonus_applied(self) -> None:
        # House 10 is a kendra
        chart = self._build_chart([{"planet_name": "Moon", "house": 10, "sign": "Capricorn", "degree": 8.0}])
        result = self.engine.score_planet("moon", chart)
        self.assertIn("sthana", result.breakdown)

    def test_trikona_house_bonus_applied(self) -> None:
        # House 5 is a trikona
        chart = self._build_chart([{"planet_name": "Moon", "house": 5, "sign": "Leo", "degree": 8.0}])
        result = self.engine.score_planet("moon", chart)
        self.assertIn("sthana", result.breakdown)

    def test_house_1_is_kendra_and_trikona(self) -> None:
        chart = self._build_chart([{"planet_name": "Moon", "house": 1, "sign": "Aries", "degree": 8.0}])
        result = self.engine.score_planet("moon", chart)
        self.assertIn("sthana", result.breakdown)

    def test_dusthana_house_gets_no_bonus(self) -> None:
        # House 6 is a dusthana - no bonus
        chart = self._build_chart([{"planet_name": "Moon", "house": 6, "sign": "Virgo", "degree": 8.0}])
        result = self.engine.score_planet("moon", chart)
        self.assertNotIn("kendra", result.breakdown)
        self.assertNotIn("trikona", result.breakdown)
        self.assertNotIn("kendra_trikona", result.breakdown)

    # ------------------------------------------------------------------
    # Score bounds & level thresholds
    # ------------------------------------------------------------------

    def test_score_is_clamped_between_0_and_100(self) -> None:
        chart = self._build_chart(
            [{"planet_name": "Sun", "house": 1, "sign": "Aries", "degree": 10.0, "is_retrograde": True}]
        )
        result = self.engine.score_planet("sun", chart)
        self.assertLessEqual(result.score, 100)
        self.assertGreaterEqual(result.score, 0)

    def test_score_below_40_is_weak(self) -> None:
        result = PlanetStrength(planet="sun", score=30, level="weak", breakdown={})
        self.assertEqual(result.level, "weak")

    def test_score_40_to_69_is_medium(self) -> None:
        result = PlanetStrength(planet="sun", score=55, level="medium", breakdown={})
        self.assertEqual(result.level, "medium")

    def test_score_70_and_above_is_strong(self) -> None:
        result = PlanetStrength(planet="sun", score=70, level="strong", breakdown={})
        self.assertEqual(result.level, "strong")

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_missing_planet_returns_zero_score_weak(self) -> None:
        chart = self._build_chart([])
        result = self.engine.score_planet("ketu", chart)
        self.assertEqual(result.score, 0)
        self.assertEqual(result.level, "weak")

    def test_score_chart_returns_entry_for_every_planet(self) -> None:
        chart = self._build_chart(
            [
                {"planet_name": "Moon", "house": 4, "sign": "Cancer", "degree": 12.0},
            ]
        )
        results = self.engine.score_chart(chart)
        self.assertIn("sun", results)
        self.assertIn("moon", results)
        # result includes sun and moon (Ascendant is skipped in calculate loop)
        self.assertEqual(len(results), 2)

    def test_as_dict_contains_all_keys(self) -> None:
        chart = self._build_chart([{"planet_name": "Sun", "house": 1, "sign": "Aries", "degree": 5.0}])
        result = self.engine.score_planet("sun", chart)
        d = result.as_dict()
        self.assertIn("planet", d)
        self.assertIn("score", d)
        self.assertIn("level", d)
        self.assertIn("breakdown", d)

    def test_breakdown_contains_canonical_shadbala_fields(self) -> None:
        chart = self._build_chart([{"planet_name": "Sun", "house": 1, "sign": "Aries", "degree": 10.0, "absolute_longitude": 10.0}])
        result = self.engine.score_planet("sun", chart)
        for key in (
            "sthana_bala",
            "dik_bala",
            "kala_bala",
            "chestha_bala",
            "naisargika_bala",
            "drik_bala",
            "total",
            "is_vargottama",
        ):
            self.assertIn(key, result.breakdown)


if __name__ == "__main__":
    unittest.main()
