import sys
import os
from pprint import pprint

# Ensure project root is in path
sys.path.append(os.getcwd())

from core.engines.astrology_engine import UnifiedAstrologyEngine
from core.yoga.models import ChartSnapshot

def verify_qualitative():
    # Mock chart data
    chart_data = [
        {"planet_name": "sun", "house": 1, "sign": "aries", "degree": 10.5},
        {"planet_name": "moon", "house": 7, "sign": "libra", "degree": 15.2},
        {"planet_name": "mars", "house": 1, "sign": "aries", "degree": 12.0},
        {"planet_name": "jupiter", "house": 4, "sign": "cancer", "degree": 5.0},
        {"planet_name": "ascendant", "house": 1, "sign": "aries", "degree": 10.0},
    ]

    engine = UnifiedAstrologyEngine()
    
    print("Running Full Analysis...")
    analysis = engine.generate_full_analysis(chart_data, dob="1990-01-01")
    
    print("\n--- NARRATIVE/TEXT ---")
    predictions = analysis.get("predictions", [])
    if predictions:
        first = predictions[0]
        print(f"Prediction: {first.get('text')}")
        
        print("\n--- QUALITATIVE TRACE ---")
        trace = first.get("trace", {})
        for layer, details in trace.items():
            if isinstance(details, dict) and "reasoning" in details:
                print(f"Layer: {layer:15} | Reasoning: {details['reasoning']}")
        
        print("\n--- ACTIVATION TRACE (EXCERPT) ---")
        activation = first.get("activation_trace", [])
        for line in activation:
            print(f" - {line}")

if __name__ == "__main__":
    verify_qualitative()
