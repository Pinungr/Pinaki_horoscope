from __future__ import annotations

import unittest

from core.engines.astrology_engine import get_house_lord_details


class HouseLordDetailsTests(unittest.TestCase):
    def test_house_lords_are_correct_for_three_lagnas(self) -> None:
        expected = {
            "aries": {
                1: "mars", 2: "venus", 3: "mercury", 4: "moon", 5: "sun", 6: "mercury",
                7: "venus", 8: "mars", 9: "jupiter", 10: "saturn", 11: "saturn", 12: "jupiter",
            },
            "taurus": {
                1: "venus", 2: "mercury", 3: "moon", 4: "sun", 5: "mercury", 6: "venus",
                7: "mars", 8: "jupiter", 9: "saturn", 10: "saturn", 11: "jupiter", 12: "mars",
            },
            "libra": {
                1: "venus", 2: "mars", 3: "jupiter", 4: "saturn", 5: "saturn", 6: "jupiter",
                7: "mars", 8: "venus", 9: "mercury", 10: "moon", 11: "sun", 12: "mercury",
            },
        }

        for lagna, expected_lords in expected.items():
            chart = [{"planet_name": "Ascendant", "sign": lagna, "house": 1, "degree": 0.0}]
            details = get_house_lord_details(chart)

            self.assertEqual(set(range(1, 13)), set(details.keys()))
            for house, lord in expected_lords.items():
                self.assertEqual(lord, details[house]["lord"])
                self.assertIn("placement", details[house])
                self.assertIn("dignity", details[house])
                self.assertIn("affliction_flags", details[house])

    def test_dual_lordship_and_exalted_debilitated_dignity(self) -> None:
        chart = [
            {"planet_name": "Ascendant", "sign": "aries", "house": 1, "degree": 0.0},
            {"planet_name": "Mars", "sign": "capricorn", "house": 10, "degree": 5.0, "absolute_longitude": 275.0},
            {"planet_name": "Venus", "sign": "virgo", "house": 6, "degree": 14.0, "absolute_longitude": 164.0},
            {"planet_name": "Sun", "sign": "leo", "house": 5, "degree": 12.0, "absolute_longitude": 132.0},
        ]
        details = get_house_lord_details(chart)

        self.assertEqual("mars", details[1]["lord"])
        self.assertEqual("mars", details[8]["lord"])
        self.assertEqual(10, details[1]["placement"]["house"])
        self.assertEqual(10, details[8]["placement"]["house"])
        self.assertEqual("exalted", details[1]["dignity"]["classification"])
        self.assertEqual("exalted", details[8]["dignity"]["classification"])

        self.assertEqual("venus", details[2]["lord"])
        self.assertEqual("venus", details[7]["lord"])
        self.assertEqual("debilitated", details[2]["dignity"]["classification"])
        self.assertEqual("debilitated", details[7]["dignity"]["classification"])

    def test_dignity_includes_friendly_and_enemy_states(self) -> None:
        chart = [
            {"planet_name": "Ascendant", "sign": "aries", "house": 1, "degree": 0.0},
            {"planet_name": "Jupiter", "sign": "leo", "house": 5, "degree": 10.0, "absolute_longitude": 130.0},
            {"planet_name": "Mercury", "sign": "cancer", "house": 4, "degree": 12.0, "absolute_longitude": 102.0},
            {"planet_name": "Sun", "sign": "aries", "house": 1, "degree": 3.0, "absolute_longitude": 3.0},
        ]
        details = get_house_lord_details(chart)

        self.assertEqual("friendly", details[9]["dignity"]["classification"])
        self.assertEqual("enemy", details[3]["dignity"]["classification"])

    def test_affliction_flags_and_structure_integrity(self) -> None:
        chart = [
            {"planet_name": "Ascendant", "sign": "aries", "house": 1, "degree": 0.0, "absolute_longitude": 0.0},
            {"planet_name": "Moon", "sign": "cancer", "house": 4, "degree": 10.0, "absolute_longitude": 100.0},
            {"planet_name": "Saturn", "sign": "cancer", "house": 4, "degree": 12.0, "absolute_longitude": 102.0},
            {"planet_name": "Mars", "sign": "aries", "house": 1, "degree": 5.0, "absolute_longitude": 5.0},
            {"planet_name": "Sun", "sign": "leo", "house": 5, "degree": 12.0, "absolute_longitude": 132.0},
            {"planet_name": "Mercury", "sign": "leo", "house": 5, "degree": 10.0, "absolute_longitude": 130.0},
            {"planet_name": "Jupiter", "sign": "sagittarius", "house": 9, "degree": 15.0, "absolute_longitude": 255.0},
        ]
        details = get_house_lord_details(chart)

        house4 = details[4]  # Moon lord
        self.assertTrue(house4["affliction_flags"]["conjunct_malefic"])
        self.assertTrue(house4["affliction_flags"]["malefic_aspect"])
        self.assertIn("saturn", house4["affliction_flags"]["malefic_conjunct_planets"])
        self.assertIn("mars", house4["affliction_flags"]["malefic_aspecting_planets"])

        house3 = details[3]  # Mercury lord
        self.assertTrue(house3["affliction_flags"]["combust"])
        self.assertTrue(house3["affliction_flags"]["is_afflicted"])

        house9 = details[9]  # Jupiter lord
        self.assertFalse(house9["affliction_flags"]["is_afflicted"])

        for house in range(1, 13):
            row = details[house]
            self.assertIn("lord", row)
            self.assertIn("placement", row)
            self.assertIn("dignity", row)
            self.assertIn("affliction_flags", row)
            self.assertIn("classification", row["dignity"])
            self.assertIn("conjunct_malefic", row["affliction_flags"])
            self.assertIn("malefic_aspect", row["affliction_flags"])
            self.assertIn("combust", row["affliction_flags"])


if __name__ == "__main__":
    unittest.main()
