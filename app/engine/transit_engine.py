from __future__ import annotations
import logging
from datetime import datetime
from typing import Dict, Any, List

import swisseph as swe
from app.models.domain import User, ChartData
from core.yoga.models import ChartSnapshot, PlanetPlacement, normalize_planet_id

logger = logging.getLogger(__name__)

class TransitEngine:
    """
    Gochar (Transit) Engine.
    Calculates current planetary positions and maps them to Natal houses.
    """

    def __init__(self):
        self._zodiac_signs = [
            "aries", "taurus", "gemini", "cancer", 
            "leo", "virgo", "libra", "scorpio", 
            "sagittarius", "capricorn", "aquarius", "pisces"
        ]

    def calculate_transits(
        self, 
        natal_chart: ChartSnapshot, 
        target_time: datetime | None = None,
        reference: str = "moon"
    ) -> Dict[str, Any]:
        """
        Calculates transits for a given time relative to a natal reference point.
        reference: "moon" (Chandra Lagna) or "lagna" (Ascendant).
        """
        if target_time is None:
            target_time = datetime.utcnow()
            
        # 1. Get current planetary positions
        transit_placements = self._get_current_positions(target_time)
        
        # 2. Get reference point sign index
        ref_planet = "moon" if reference.lower() == "moon" else "ascendant"
        natal_ref = natal_chart.get(ref_planet)
        
        if not natal_ref:
            logger.warning("Natal reference point '%s' not found for transit calculation.", ref_planet)
            return {"transits": {}, "reference": reference}
            
        ref_sign_idx = self._zodiac_signs.index(natal_ref.sign.lower())
        
        # 3. Map transits to relative houses
        transits_output = {}
        for p_id, p_dict in transit_placements.items():
            p_long = p_dict["long"]
            p_sign_idx = int(p_long / 30)
            relative_house = (p_sign_idx - ref_sign_idx) % 12 + 1
            
            transits_output[p_id] = {
                "sign": self._zodiac_signs[p_sign_idx],
                "house_from_reference": relative_house,
                "absolute_longitude": round(p_long, 4),
                "is_retrograde": p_dict["is_retrograde"]
            }
            
        return {
            "transits": transits_output,
            "reference": reference,
            "target_time": target_time.isoformat()
        }

    def _get_current_positions(self, target_time: datetime) -> Dict[str, dict]:
        """Calculates geocentric sidereal longitudes and motional status."""
        jd_ut = swe.julday(
            target_time.year, target_time.month, target_time.day,
            target_time.hour + target_time.minute / 60.0 + target_time.second / 3600.0
        )
        
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL
        
        planets = {
            "sun": swe.SUN, "moon": swe.MOON, "mars": swe.MARS, 
            "mercury": swe.MERCURY, "jupiter": swe.JUPITER, 
            "venus": swe.VENUS, "saturn": swe.SATURN, "rahu": swe.MEAN_NODE
        }
        
        results = {}
        for name, p_idx in planets.items():
            res, _ = swe.calc_ut(jd_ut, p_idx, flags)
            results[name] = {"long": res[0], "is_retrograde": res[3] < 0}
            
            if name == "rahu":
                results["ketu"] = {"long": (res[0] + 180.0) % 360.0, "is_retrograde": res[3] < 0}
                
        return results
