import unittest
from datetime import datetime
from unittest.mock import patch

from app.engine.transit_engine import TransitEngine
from core.yoga.models import ChartSnapshot, PlanetPlacement

class TransitEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = TransitEngine()

    def test_relative_house_calculation(self):
        # Natal Moon in Aries ($0^\circ-30^\circ$)
        natal_moon = PlanetPlacement(
            planet="moon", house=1, sign="aries", degree=10, absolute_longitude=10.0, is_retrograde=False
        )
        natal_chart = ChartSnapshot(placements={"moon": natal_moon})
        
        # Date where Saturn is in Aries (house 1 from Aries Moon)
        # Jan 1st 2026
        target_time = datetime(2026, 1, 1, 12, 0, 0)
        
        result = self.engine.calculate_transits(natal_chart, target_time, reference="moon")
        saturn_transit = result["transits"].get("saturn")
        
        # Saturn is in Pisces (Index 11) on Jan 1st 2026.
        # (11 - 0) % 12 + 1 = 12
        self.assertEqual(saturn_transit["house_from_reference"], 12)
        self.assertEqual(saturn_transit["sign"], "pisces")
        self.assertIn("is_retrograde", saturn_transit)

    def test_sade_sati_logic_in_engine(self):
        # Natal Moon in Aquarius (index 10)
        natal_moon = PlanetPlacement(
            planet="moon", house=1, sign="aquarius", degree=15, absolute_longitude=315.0, is_retrograde=False
        )
        natal_chart = ChartSnapshot(placements={"moon": natal_moon})
        
        # Current Saturn in Aquarius (index 10) -> Jan 1st 2024
        target_time = datetime(2024, 1, 1, 12, 0, 0)
        
        result = self.engine.calculate_transits(natal_chart, target_time, reference="moon")
        saturn_transit = result["transits"].get("saturn")
        
        # Relative house should be 1 (Peak Sade Sati)
        self.assertEqual(saturn_transit["house_from_reference"], 1)

    def test_rahu_ketu_opposite(self):
        results = self.engine._get_current_positions(datetime.utcnow())
        rahu = results["rahu"]["long"]
        ketu = results["ketu"]["long"]
        
        # Ketu must be exactly 180 degrees from Rahu
        diff = abs(rahu - ketu)
        self.assertTrue(abs(diff - 180.0) < 0.001 or abs(diff - 180.0) > 359.999)

    def test_dual_reference_payload_separates_lagna_and_moon_views(self):
        natal_chart = ChartSnapshot(
            placements={
                "ascendant": PlanetPlacement(
                    planet="ascendant",
                    house=1,
                    sign="aries",
                    degree=5.0,
                    absolute_longitude=5.0,
                    is_retrograde=False,
                ),
                "moon": PlanetPlacement(
                    planet="moon",
                    house=4,
                    sign="cancer",
                    degree=5.0,
                    absolute_longitude=95.0,
                    is_retrograde=False,
                ),
            }
        )

        mocked_positions = {
            "sun": {"long": 95.0, "is_retrograde": False},   # Cancer
            "saturn": {"long": 275.0, "is_retrograde": True},  # Capricorn
            "rahu": {"long": 10.0, "is_retrograde": True},
            "ketu": {"long": 190.0, "is_retrograde": True},
        }

        with patch.object(self.engine, "_get_current_positions", return_value=mocked_positions):
            result = self.engine.calculate_transits(natal_chart, datetime(2026, 1, 1, 12, 0, 0), reference="both")

        self.assertEqual("both", result["reference"])
        self.assertIn("from_lagna", result)
        self.assertIn("from_moon", result)
        self.assertIn("transit_matrix", result)
        self.assertIn("sun", result["transit_matrix"])

        sun_row = result["transit_matrix"]["sun"]
        self.assertIn("from_lagna", sun_row)
        self.assertIn("from_moon", sun_row)
        self.assertNotEqual(
            sun_row["from_lagna"]["house_position"],
            sun_row["from_moon"]["house_position"],
        )
        self.assertEqual(4, sun_row["from_lagna"]["house_position"])
        self.assertEqual(1, sun_row["from_moon"]["house_position"])

    def test_dual_reference_payload_matches_when_lagna_equals_moon_sign(self):
        natal_chart = ChartSnapshot(
            placements={
                "ascendant": PlanetPlacement(
                    planet="ascendant",
                    house=1,
                    sign="aries",
                    degree=5.0,
                    absolute_longitude=5.0,
                    is_retrograde=False,
                ),
                "moon": PlanetPlacement(
                    planet="moon",
                    house=1,
                    sign="aries",
                    degree=15.0,
                    absolute_longitude=15.0,
                    is_retrograde=False,
                ),
            }
        )
        mocked_positions = {
            "jupiter": {"long": 125.0, "is_retrograde": False},  # Leo
            "saturn": {"long": 275.0, "is_retrograde": True},   # Capricorn
            "rahu": {"long": 10.0, "is_retrograde": True},
            "ketu": {"long": 190.0, "is_retrograde": True},
        }

        with patch.object(self.engine, "_get_current_positions", return_value=mocked_positions):
            result = self.engine.calculate_transits(natal_chart, datetime(2026, 1, 1, 12, 0, 0), reference="both")

        jupiter = result["transit_matrix"]["jupiter"]
        self.assertEqual(
            jupiter["from_lagna"]["house_position"],
            jupiter["from_moon"]["house_position"],
        )
        self.assertEqual(
            result["from_lagna"]["jupiter"]["house_from_reference"],
            result["from_moon"]["jupiter"]["house_from_reference"],
        )

if __name__ == "__main__":
    unittest.main()
