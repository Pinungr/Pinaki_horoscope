from typing import Dict, Any, List
from app.engine.varga_engine import VargaEngine

class NavamshaEngine:
    """Calculates Navamsha (D9) Chart placements using high-precision integer math."""

    def __init__(self):
        self.varga = VargaEngine()

    def get_navamsha_sign(self, sign_name: str, degree: float) -> str:
        """Calculates the D9 sign for a single placement."""
        return self.varga.get_varga_sign(9, sign_name, degree)

    def calculate_navamsha(self, chart_data: Dict[str, Dict[str, Any]] | List[Any]) -> Dict[str, Dict[str, str]]:
        """Calculates D9 signs for all planets in the chart data."""
        results = {}
        
        # Determine if chart_data is a list of objects or a legacy dict
        items = []
        if isinstance(chart_data, list):
            items = chart_data
        elif isinstance(chart_data, dict):
            for name, d in chart_data.items():
                items.append({"planet_name": name, "sign": d.get("sign"), "degree": d.get("degree")})
        
        varga_results = self.varga.calculate_varga_chart(9, items)
        for planet, sign in varga_results.items():
            results[planet] = {"navamsha_sign": sign}
            
        return results
