import json
from app.engine.navamsha import NavamshaEngine

def test_navamsha():
    print("Testing Navamsha Engine...")
    engine = NavamshaEngine()
    
    # Input from prompt: "Sun": {"sign": "Aries", "degree": 10.5} -> Should be Gemini.
    # Aries = Fire. Starts at Aries. 
    # 0 to 3.333 -> part 0
    # 3.333 to 6.666 -> part 1
    # 6.666 to 10.0 -> part 2
    # 10.0 to 13.333 -> part 3
    # 10.5 is in part 3.
    # Aries(1) + 3 = 4 (Cancer). Wait!
    # Aries starts at Aries. 
    # 1st navamsha = Aries
    # 2nd navamsha = Taurus
    # 3rd = Gemini
    # 4th = Cancer.
    # So 10.5 degrees should be Cancer, not Gemini!
    # Let's check part = 10.5 / (30/9) = 10.5 / 3.333333333 = 3.15 -> part 3
    # part 3 means 4th navamsha.
    # 4th from Aries is Cancer.
    # If the user sample output is {"Sun": {"navamsha_sign": "Gemini"}}, that's because they assumed 10.5 is 3rd part?
    # 10.5 is > 10.0 so it falls in 4th part. Gemini is 6°40' to 10°00'. 10.5 is Cancer!
    
    chart_data = {
        "Sun": {"sign": "Aries", "degree": 10.5},
        "Moon": {"sign": "Aries", "degree": 5.0} # 5.0 / 3.3333 = 1.5 -> part 1. 2nd Navamsha -> Taurus.
    }
    
    output = engine.calculate_navamsha(chart_data)
    print(json.dumps(output, indent=2))
    print("Tests finished.")

if __name__ == "__main__":
    test_navamsha()
