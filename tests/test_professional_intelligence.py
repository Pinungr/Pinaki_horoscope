import unittest
from core.engines.functional_nature import FunctionalNatureEngine
from core.yoga.models import ChartSnapshot, PlanetPlacement
from core.engines.shadbala.drik_bala import DrikBalaCalculator

class ProfessionalIntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.functional = FunctionalNatureEngine()
        self.drik = DrikBalaCalculator()

    def test_functional_roles_libra_lagna(self):
        # Libra Lagna (Index 6)
        # Saturn rules 4 (Cap) and 5 (Aqu) -> Kendra + Trikona -> Yogakaraka
        # Jupiter rules 3 (Sag) and 6 (Pis) -> Malefic
        roles = self.functional.get_planet_roles("libra")
        self.assertEqual(roles["saturn"], "yogakaraka")
        self.assertEqual(roles["jupiter"], "malefic")
        self.assertEqual(roles["moon"], "benefic") # Rules 10 (Cancer) - Kendra lord moon is often benefic enough in this logic

    def test_functional_roles_leo_lagna(self):
        # Leo Lagna (Index 4)
        # Mars rules 4 (Sco) and 9 (Ari) -> Kendra + Trikona -> Yogakaraka
        roles = self.functional.get_planet_roles("leo")
        self.assertEqual(roles["mars"], "yogakaraka")

    def test_drik_bala_jupiter_aspect(self):
        # Sun at 0 (Aries)
        # Jupiter at 120 (Leo) -> 5th house aspect on Sun
        chart = ChartSnapshot(placements={
            "sun": PlanetPlacement(planet="sun", house=1, sign="aries", absolute_longitude=0.0),
            "jupiter": PlanetPlacement(planet="jupiter", house=5, sign="leo", absolute_longitude=120.0)
        })
        
        sun_drik = self.drik.calculate("sun", chart)
        # Full aspect (60) from Benefic (Jupiter). In calculator: total_drik / 4.0 = 60 / 4 = 15.0
        self.assertEqual(sun_drik, 15.0)

    def test_drik_bala_saturn_aspect(self):
        # Sun at 0 (Aries)
        # Saturn at 300 (Capricorn) -> 3rd house aspect on Aries (300 + 60 = 360/0)
        # Wait, Saturn aspect on 3rd is 60 deg away. 
        # If Saturn is at 300, Sun at 0. Distance = (0 - 300) % 360 = 60.
        chart = ChartSnapshot(placements={
            "sun": PlanetPlacement(planet="sun", house=3, sign="aries", absolute_longitude=0.0),
            "saturn": PlanetPlacement(planet="saturn", house=1, sign="capricorn", absolute_longitude=300.0)
        })
        
        sun_drik = self.drik.calculate("sun", chart)
        # Full aspect (60) from Malefic (Saturn). 
        # (Aspect of Benefic - Aspect of Malefic) / 4 = -60 / 4 = -15.0
        self.assertEqual(sun_drik, -15.0)

if __name__ == "__main__":
    unittest.main()
