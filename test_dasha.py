import json
from app.engine.dasha import DashaEngine

def test_dasha():
    print("Testing Dasha Engine...")
    engine = DashaEngine()
    
    moon_long = 120.0  # Exactly 9 times Nakshatra Arc (9 * 13.333...) -> Magha Nakshatra -> Ketu starts. Wait: 120 / 13.333 = 8.99999.
    moon_long = 120.0001 # index 9 -> Nakshatra 10 -> Lord is Ketu (starts again)
    
    # Let's test a simple one: Krittika Nakshatra (Index 2, Lord Sun (6 yrs)).
    # Krittika spans 26.666 to 40.0 degrees. (Index 2).
    # Midpoint = 33.333
    moon_long = 33.3333333333333
    
    timeline = engine.calculate_dasha(moon_long, "1994-07-28")
    print(json.dumps(timeline, indent=2))
    print("Tests finished.")

if __name__ == "__main__":
    test_dasha()
