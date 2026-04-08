from typing import Dict, Any

class NavamshaEngine:
    """Calculates Navamsha (D9) Chart Sign placements based on birth chart degrees."""

    signs = [
        "aries", "taurus", "gemini", "cancer", "leo", "virgo",
        "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces"
    ]
    
    element_start_idx = {
        1: 1, 5: 1, 9: 1,      # Fire starts at Aries
        2: 10, 6: 10, 10: 10,  # Earth starts at Capricorn
        3: 7, 7: 7, 11: 7,     # Air starts at Libra
        4: 4, 8: 4, 12: 4      # Water starts at Cancer
    }

    @staticmethod
    def get_navamsha_sign(sign_name: str, degree: float) -> str:
        """Calculates the D9 sign for a single placement."""
        sign_name = sign_name.lower().strip()
        if sign_name not in NavamshaEngine.signs:
            return ""
            
        sign_idx = NavamshaEngine.signs.index(sign_name) + 1
        
        # 12,000 arc-seconds per Navamsha part (1/9th of 30 deg)
        total_arc_seconds = int(round(degree * 3600))
        part = total_arc_seconds // 12000
        part = min(max(0, part), 8)
        
        start_sign_idx = NavamshaEngine.element_start_idx[sign_idx]
        d9_idx = (start_sign_idx - 1 + part) % 12
        return NavamshaEngine.signs[d9_idx]

    def calculate_navamsha(self, chart_data: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
        """Backwards compatible batch calculator."""
        results = {}
        for planet, data in chart_data.items():
            sign = data.get("sign")
            degree = data.get("degree")
            if sign and degree is not None:
                d9_sign = self.get_navamsha_sign(sign, degree)
                if d9_sign:
                    # Return capitalized for legacy UI compatibility if needed, 
                    # but engine prefers lower. Let's return as calculated.
                    results[planet] = {"navamsha_sign": d9_sign.capitalize()}
        return results
