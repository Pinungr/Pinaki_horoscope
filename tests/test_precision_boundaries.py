import unittest
from app.engine.navamsha import NavamshaEngine
from app.engine.dasha import DashaEngine

class TestPrecision(unittest.TestCase):
    def test_navamsha_boundary(self):
        engine = NavamshaEngine()
        # 3 degrees 20 minutes is exactly the boundary between part 0 and part 1
        # Part 0 (Aries-Aries) ends at 3.333333333333333...
        # Part 1 (Aries-Taurus) starts there.
        
        # Slightly before boundary
        res1 = engine.get_navamsha_sign("Aries", 3.3333)
        # Slightly after boundary
        res2 = engine.get_navamsha_sign("Aries", 3.3334)
        # EXACTLY on boundary (using float that might drift)
        res3 = engine.get_navamsha_sign("Aries", 3.333333333333333)
        
        print(f"Navamsha 3.3333: {res1}")
        print(f"Navamsha 3.3334: {res2}")
        print(f"Navamsha 3.333333333333333: {res3}")
        
        self.assertEqual(res1, "aries")
        self.assertEqual(res2, "taurus")
        # In professional astrology, the boundary point typically belongs to the NEW division
        self.assertEqual(res3, "taurus")

    def test_dasha_boundary(self):
        engine = DashaEngine()
        # 13 degrees 20 minutes = 13.333333333333333... degrees
        # This is the boundary between Nakshatra 0 and 1.
        
        # Just before boundary
        timeline1 = engine.calculate_dasha(13.3333, "2000-01-01")
        # Just after
        timeline2 = engine.calculate_dasha(13.3334, "2000-01-01")
        # Exactly on
        timeline3 = engine.calculate_dasha(13.333333333333333, "2000-01-01")
        
        print(f"Dasha 13.3333 starts with: {timeline1[0]['planet']}")
        print(f"Dasha 13.3334 starts with: {timeline2[0]['planet']}")
        print(f"Dasha 13.333333333333333 starts with: {timeline3[0]['planet']}")
        
        # Nakshatra 0 is Ashwini (Ketu)
        # Nakshatra 1 is Bharani (Venus)
        self.assertEqual(timeline1[0]['planet'], "Ketu")
        self.assertEqual(timeline2[0]['planet'], "Venus")
        self.assertEqual(timeline3[0]['planet'], "Venus")

if __name__ == "__main__":
    unittest.main()
