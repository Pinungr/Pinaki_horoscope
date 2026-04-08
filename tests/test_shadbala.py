import unittest
from core.yoga.models import ChartSnapshot
from core.engines.shadbala.shadbala_aggregator import ShadbalaEngine

class TestShadbala(unittest.TestCase):
    def setUp(self):
        self.engine = ShadbalaEngine()

    def test_sthana_bala_exaltation(self):
        # Sun at 10 Aries (Absolute 10) is deep exaltation
        chart = ChartSnapshot.from_rows([
            {"planet_name": "Sun", "house": 1, "sign": "Aries", "degree": 10.0, "absolute_longitude": 10.0},
            {"planet_name": "Ascendant", "house": 1, "sign": "Aries", "degree": 0.0, "absolute_longitude": 0.0}
        ])
        result = self.engine.calculate(chart)
        sun_strength = result.planets["sun"]
        
        # Sthana = Ucha(60) + Kendra(60) + Odd/Even(15) = 135
        self.assertEqual(sun_strength.sthana_bala, 135.0)

    def test_dik_bala_jupiter_in_1st(self):
        # Jupiter in 1st house gets full Dik Bala
        chart = ChartSnapshot.from_rows([
            {"planet_name": "Sun", "house": 2, "sign": "Taurus", "degree": 10.0, "absolute_longitude": 40.0},
            {"planet_name": "Jupiter", "house": 1, "sign": "Aries", "degree": 0.0, "absolute_longitude": 0.0},
            {"planet_name": "Ascendant", "house": 1, "sign": "Aries", "degree": 0.0, "absolute_longitude": 0.0}
        ])
        result = self.engine.calculate(chart)
        jupiter_strength = result.planets["jupiter"]
        
        # Dik Bala for Jupiter in 1st is 60
        self.assertEqual(jupiter_strength.dik_bala, 60.0)

    def test_naisargika_bala_sun_is_max(self):
        chart = ChartSnapshot.from_rows([
            {"planet_name": "Sun", "house": 1, "sign": "Aries", "degree": 0.0, "absolute_longitude": 0.0},
            {"planet_name": "Ascendant", "house": 1, "sign": "Aries", "degree": 0.0, "absolute_longitude": 0.0}
        ])
        result = self.engine.calculate(chart)
        self.assertEqual(result.planets["sun"].naisargika_bala, 60.0)
        
if __name__ == '__main__':
    unittest.main()
