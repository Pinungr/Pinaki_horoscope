from app.engine.navamsha import NavamshaEngine

engine = NavamshaEngine()

# Theoretical boundary is 3.333333333...
# Let's test precisely at and near boundaries
test_cases = [
    {"sign": "Aries", "degree": 3.333333333333333}, # Should be part 0 or 1?
    {"sign": "Aries", "degree": 3.333333333333334}, # Should be part 1
    {"sign": "Aries", "degree": 0.0},                # Should be part 0 (Aries)
    {"sign": "Aries", "degree": 29.999999},        # Should be part 8 (Sagittarius)
]

for tc in test_cases:
    res = engine.calculate_navamsha({"Test": tc})
    print(f"Degree: {tc['degree']} -> Navamsha: {res['Test']['navamsha_sign']}")

# Calculation:
# Aries (Fire) starts at Aries.
# Parts: 0: 0-3.33, 1: 3.33-6.66, 2: 6.66-10.0 ...
