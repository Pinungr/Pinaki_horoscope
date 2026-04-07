from typing import Dict, Any

class NavamshaEngine:
    """Calculates Navamsha (D9) Chart Sign placements based on birth chart degrees."""

    def __init__(self):
        # Ordered list of Zodiac signs (1-indexed mapping)
        self.signs = [
            "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
            "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
        ]
        
        # Reverse lookup mapping sign name to its 1-index position
        self.sign_to_idx = {name: idx + 1 for idx, name in enumerate(self.signs)}
        
        # Vedic mathematical law for D9 starting points:
        # Fire signs (1, 5, 9) start at Aries (1)
        # Earth signs (2, 6, 10) start at Capricorn (10)
        # Air signs (3, 7, 11) start at Libra (7)
        # Water signs (4, 8, 12) start at Cancer (4)
        self.element_start_idx = {
            1: 1, 5: 1, 9: 1,
            2: 10, 6: 10, 10: 10,
            3: 7, 7: 7, 11: 7,
            4: 4, 8: 4, 12: 4
        }
        
    def calculate_navamsha(self, chart_data: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
        """
        Input: {"Sun": {"sign": "Aries", "degree": 10.5}}
        Output: {"Sun": {"navamsha_sign": "Gemini"}}
        """
        results = {}
        for planet, data in chart_data.items():
            sign = data.get("sign")
            degree = data.get("degree")
            
            if not sign or degree is None:
                continue
                
            sign_idx = self.sign_to_idx.get(sign)
            if not sign_idx:
                continue
                
            # Navamsha part logic: 30 degrees broken into 9 parts = 3.333333 degrees per part
            # Find which of the 9 chunks (0-8) the planet falls into
            part = int(degree / (30.0 / 9.0))
            if part >= 9:
                part = 8 # fail-safe bound
                
            # Determine starting sign index
            start_sign_idx = self.element_start_idx[sign_idx]
            
            # Calculate final D9 sign index (circular 1-12)
            d9_idx = (start_sign_idx - 1 + part) % 12 + 1
            
            results[planet] = {"navamsha_sign": self.signs[d9_idx - 1]}
            
        return results
