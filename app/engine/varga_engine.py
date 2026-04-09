import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class VargaEngine:
    """
    Unified high-precision division engine for Varga (Divisional) charts.
    Uses integer-based arc-seconds to eliminate floating-point boundary drift.
    """

    SIGNS = [
        "aries", "taurus", "gemini", "cancer", "leo", "virgo",
        "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces"
    ]
    
    # Starting sign for each element type in Navamsha (D9)
    # Fire (1,5,9) -> Aries(1); Earth (2,6,10) -> Capricorn(10); 
    # Air (3,7,11) -> Libra(7); Water (4,8,12) -> Cancer(4)
    ELEMENT_START_IDX = {
        1: 1, 5: 1, 9: 1,
        2: 10, 6: 10, 10: 10,
        3: 7, 7: 7, 11: 7,
        4: 4, 8: 4, 12: 4
    }

    @staticmethod
    def _read_value(payload: Any, key: str, default: Any = None) -> Any:
        if isinstance(payload, dict):
            return payload.get(key, default)
        return getattr(payload, key, default)

    def _iter_normalized_rows(self, chart_data: List[Any]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for cd in chart_data or []:
            raw_planet = self._read_value(cd, "planet_name", self._read_value(cd, "planet"))
            raw_sign = self._read_value(cd, "sign")
            raw_degree = self._read_value(cd, "degree")

            planet = str(raw_planet or "").strip()
            sign = str(raw_sign or "").strip().lower()
            if not planet or sign not in self.SIGNS:
                continue
            try:
                degree = float(raw_degree)
            except (TypeError, ValueError):
                continue

            rows.append(
                {
                    "planet_name": planet,
                    "planet": planet.lower(),
                    "sign": sign,
                    "degree": degree % 30.0,
                }
            )
        return rows

    @staticmethod
    def _to_arc_seconds(degree: float) -> int:
        """Converts float degrees to integer arc-seconds with epsilon-safe floor."""
        # We use a tiny epsilon (0.0001 arc-seconds) to handle floating point 
        # approximations of exact boundaries (like 3.333333333333333).
        # This ensures that exact boundary points fall into the higher division.
        import math
        return int(math.floor(degree * 3600 + 1e-6))

    def get_varga_sign(self, varga_factor: int, sign_name: str, degree: float) -> str:
        """
        Calculates the sign for a given varga division.
        Supports:
        - D9 (Navamsha)
        - D10 (Dashamsha)
        - D60 (Shastiamsha)
        """
        sign_name = sign_name.lower().strip()
        if sign_name not in self.SIGNS:
            return ""
            
        rashi_idx = self.SIGNS.index(sign_name) + 1  # 1-based
        arc_sec = self._to_arc_seconds(degree % 30)  # Relative to sign start
        
        # Duration of one division in arc-seconds
        # 30 degrees = 108,000 arc-seconds
        div_duration = 108000 // varga_factor
        
        # Which division part (0 to varga_factor - 1)
        part = arc_sec // div_duration
        # Safety clamp for edge cases like exactly 30.0
        part = min(max(0, part), varga_factor - 1)
        
        if varga_factor == 9:
            # Special Navamsha logic (Element based)
            start_sign_idx = self.ELEMENT_START_IDX[rashi_idx]
            varga_idx = (start_sign_idx - 1 + part) % 12
        elif varga_factor == 60:
            # Shastiamsha: Standard 60 divisions
            # Count starts from the sign itself
            varga_idx = (rashi_idx - 1 + part) % 12
        else:
            # Default cyclic logic used for most other vargas (D10, D12, etc.)
            varga_idx = (rashi_idx - 1 + part) % 12
            
        return self.SIGNS[varga_idx]

    def calculate_varga_chart(self, varga_factor: int, chart_data: List[Any]) -> Dict[str, str]:
        """Calculates varga placements for a set of planetary data objects."""
        results = {}
        for row in self._iter_normalized_rows(chart_data):
            v_sign = self.get_varga_sign(varga_factor, row["sign"], row["degree"])
            if not v_sign:
                continue
            results[row["planet_name"]] = v_sign.capitalize()
        return results

    def get_d10_chart(self, natal_chart: List[Any]) -> Dict[str, Any]:
        """
        Computes Dashamsha (D10) chart projection from D1 rows.

        Output:
        {
            "ascendant_sign": "aries",
            "rows": [{"planet_name", "sign", "house", "degree"}, ...],
            "placements": {"sun": {"sign", "house", "degree"}, ...}
        }
        """
        rows = self._iter_normalized_rows(natal_chart)
        if not rows:
            return {"ascendant_sign": "", "rows": [], "placements": {}}

        d10_rows: List[Dict[str, Any]] = []
        ascendant_sign = ""
        for row in rows:
            d10_sign = self.get_varga_sign(10, row["sign"], row["degree"])
            if not d10_sign:
                continue

            planet_id = str(row["planet"]).strip().lower()
            if planet_id in {"ascendant", "lagna"}:
                ascendant_sign = d10_sign

            d10_rows.append(
                {
                    "planet_name": row["planet_name"],
                    "sign": d10_sign,
                    "degree": round(row["degree"], 4),
                }
            )

        if not d10_rows:
            return {"ascendant_sign": "", "rows": [], "placements": {}}

        if not ascendant_sign:
            # Fallback when Ascendant input is unavailable.
            ascendant_sign = str(d10_rows[0]["sign"]).strip().lower()

        asc_idx = self.SIGNS.index(ascendant_sign)
        placements: Dict[str, Dict[str, Any]] = {}
        for row in d10_rows:
            sign = str(row["sign"]).strip().lower()
            sign_idx = self.SIGNS.index(sign)
            house = ((sign_idx - asc_idx) % 12) + 1
            row["house"] = house

            planet_id = str(row["planet_name"]).strip().lower()
            placements[planet_id] = {
                "sign": sign,
                "house": house,
                "degree": row["degree"],
            }

        return {
            "ascendant_sign": ascendant_sign,
            "rows": d10_rows,
            "placements": placements,
        }
