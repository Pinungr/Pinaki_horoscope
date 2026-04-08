import json
from app.models.domain import ChartData
from core.engines.aspect_engine import calculate_aspects

def run_tests():
    print("--- Starting Aspects Engine Tests ---")

    sample_chart = [
        ChartData(user_id=1, planet_name="Saturn", sign="Gemini", house=3, degree=10.0),
        ChartData(user_id=1, planet_name="Moon", sign="Leo", house=5, degree=12.0),
        ChartData(user_id=1, planet_name="Jupiter", sign="Scorpio", house=9, degree=18.5),
        ChartData(user_id=1, planet_name="Mars", sign="Pisces", house=12, degree=2.3),
    ]

    printable_input = [
        {"planet_name": item.planet_name, "house": item.house}
        for item in sample_chart
    ]
    print(f"Input Data:\n{json.dumps(printable_input, indent=2)}\n")

    output = calculate_aspects(sample_chart)
    print(f"Output Aspects:\n{json.dumps(output, indent=2)}\n")

    assert {"from": "Saturn", "to": "Moon", "from_house": 3, "to_house": 5, "aspect_type": "drishti"} in output, "Saturn to Moon aspect missing!"
    assert {"from": "Jupiter", "to": "Saturn", "from_house": 9, "to_house": 3, "aspect_type": "drishti"} in output, "Jupiter to Saturn aspect missing!"
    
    print("--- Tests Passed Successfully ---")

if __name__ == "__main__":
    run_tests()
