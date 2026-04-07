import json
from app.engine.aspects import AspectsEngine

def run_tests():
    print("--- Starting Aspects Engine Tests ---")
    
    engine = AspectsEngine()
    
    # Input definition from instructions
    sample_chart = {
        "Saturn": {"house": 10},
        "Moon": {"house": 4},
        "Mars": {"house": 1},
        "Jupiter": {"house": 2} # Jupiter in 2 expected aspects: 2+4=6, 2+6=8, 2+8=10 -> 6, 8, 10
    }
    
    print(f"Input Data:\n{json.dumps(sample_chart, indent=2)}\n")
    
    output = engine.calculate_aspects(sample_chart)
    print(f"Output Aspects:\n{json.dumps(output, indent=2)}\n")
    
    # Assertions based on rules
    saturn_aspects = [x["aspect_house"] for x in output["Saturn"]]
    assert set(saturn_aspects) == {12, 4, 7}, "Saturn aspects test failed!"
    
    moon_aspects = [x["aspect_house"] for x in output["Moon"]]
    assert set(moon_aspects) == {10}, "Moon 7th aspect test failed!"
    
    print("--- Tests Passed Successfully ---")

if __name__ == "__main__":
    run_tests()
