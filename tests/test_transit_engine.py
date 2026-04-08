import unittest
from datetime import datetime
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

if __name__ == "__main__":
    unittest.main()
