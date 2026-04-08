import unittest
from core.engines.shadbala.sthana_bala import calculate_sthana_bala
from core.yoga.models import PlanetPlacement, ChartSnapshot
from core.engines.shadbala.shadbala_aggregator import ShadbalaEngine

class CrossVargaSynthesisTests(unittest.TestCase):
    def setUp(self):
        self.engine = ShadbalaEngine()

    def test_vargottama_bonus(self):
        # Sun at 1 degree Aries (D1: Aries, D9: Aries) -> Vargottama
        placement = PlanetPlacement(
            planet="sun", house=1, sign="aries", degree=1.0, absolute_longitude=1.0
        )
        
        # Calculate base Sthana Bala (Exaltation in Aries + Kendra)
        # Exaltation at 10 deg. Diff = 9. 60 * (1 - 9/180) = 57.0
        # Kendra = 60.0
        # Ojha-Yugma (Sun in Aries) = 15.0
        # Vargottama = 45.0
        # D9 Exaltation (Sun in Aries in D9) = 30.0
        # Total = 57 + 60 + 15 + 45 + 30 = 207.0
        
        sthana = calculate_sthana_bala("sun", placement)
        self.assertEqual(sthana, 207.0)

    def test_vargottama_flag(self):
        # Sun at 1 degree Aries
        chart = ChartSnapshot(placements={
            "sun": PlanetPlacement(planet="sun", house=1, sign="aries", degree=1.0, absolute_longitude=1.0),
            "ascendant": PlanetPlacement(planet="ascendant", house=1, sign="aries", degree=10.0, absolute_longitude=10.0)
        })
        
        result = self.engine.calculate(chart)
        sun_shadbala = result.planets["sun"]
        self.assertTrue(sun_shadbala.is_vargottama)

    def test_d9_debilitation_penalty(self):
        # Sun in Aries (Exalted in D1)
        # But in a degree that falls into Libra in D9 (Debilitated in D9)
        # Aries 20 deg to 23 deg 20 min -> 7th Navamsha (Libra)
        # Degree 21.0
        placement = PlanetPlacement(
            planet="sun", house=1, sign="aries", degree=21.0, absolute_longitude=21.0
        )
        
        # Exaltation: Diff from 10 = 11. 60 * (1 - 11/180) = 56.33
        # Kendra = 60
        # Ojha = 15
        # D9 Debilitation = -30
        # Total = 56.33 + 60 + 15 - 30 = 101.33
        
        sthana = calculate_sthana_bala("sun", placement)
        self.assertAlmostEqual(sthana, 101.33, places=2)

if __name__ == "__main__":
    unittest.main()
