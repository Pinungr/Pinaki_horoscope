from __future__ import annotations
from typing import Dict
from core.yoga.models import ChartSnapshot, PlanetPlacement, normalize_planet_id
from app.engine.navamsha import NavamshaEngine
from core.engines.dignity_engine import DignityEngine

# Deep Exaltation points (Absolute Longitude)
DEEP_EXALTATION: Dict[str, float] = {
    "sun": 10.0,      # Aries 10
    "moon": 33.0,     # Taurus 3
    "mars": 298.0,    # Capricorn 28
    "mercury": 165.0, # Virgo 15
    "jupiter": 95.0,  # Cancer 5
    "venus": 357.0,   # Pisces 27
    "saturn": 200.0,  # Libra 20
    "rahu": 65.0,     # Gemini 5 (Approx classical)
    "ketu": 245.0,    # Sagittarius 5 (Approx classical)
}

def calculate_sthana_bala(
    planet: str, 
    placement: PlanetPlacement, 
    sun_placement: PlanetPlacement | None = None
) -> float:
    """
    Calculates Sthana Bala (Positional Strength) components.
    Currently includes Ucha Bala, Kendra Bala, and Ojha-Yugma Bala.
    """
    planet_id = normalize_planet_id(planet)
    total_sthana = 0.0
    
    # 1. Ucha Bala (Exaltation)
    # 60 Virupas at deep exaltation, 0 at 180 degrees away.
    if planet_id in DEEP_EXALTATION:
        exalt_point = DEEP_EXALTATION[planet_id]
        diff = abs(placement.absolute_longitude - exalt_point)
        if diff > 180:
            diff = 360 - diff
        
        # Formula: 60 * (1 - diff/180)
        ucha_bala = max(0.0, 60.0 * (1.0 - (diff / 180.0)))
        total_sthana += ucha_bala

    # 2. Kendra Bala (House Strength)
    # Angle: 60, Panapara (Succedent): 30, Apoklima (Cadent): 15
    house = placement.house
    if house in {1, 4, 7, 10}:
        total_sthana += 60.0
    elif house in {2, 5, 8, 11}:
        total_sthana += 30.0
    elif house in {3, 6, 9, 12}:
        total_sthana += 15.0

    # 3. Ojha-Yugma Bala (Odd/Even signs)
    # Sun, Mars, Jupiter = 15 in Odd (Aries, etc.)
    # Moon, Mercury, Venus, Saturn = 15 in Even (Taurus, etc.)
    odd_signs = {"aries", "gemini", "leo", "libra", "sagittarius", "aquarius"}
    sign = placement.sign.lower()
    is_odd = sign in odd_signs
    
    ojha_yugma = 0.0
    if planet_id in {"sun", "mars", "jupiter"}:
        if is_odd:
            ojha_yugma = 15.0
    elif planet_id in {"moon", "mercury", "venus", "saturn"}:
        if not is_odd:
            ojha_yugma = 15.0
    total_sthana += ojha_yugma
    
    # 4. Combustion (Strict mathematical penalty)
    if sun_placement and planet_id != "sun":
        # Classical orbs
        orbs = {"moon": 12, "mars": 17, "mercury": 14, "jupiter": 11, "venus": 10, "saturn": 15}
        orb = orbs.get(planet_id)
        if orb:
            delta = abs(placement.absolute_longitude - sun_placement.absolute_longitude)
            if min(delta, 360 - delta) <= orb:
                # In Shadbala, combustion is a heavy divider/penalty. 
                # For simplified MVP, we subtract 60 Virupas.
                total_sthana -= 60.0

    # 5. Cross-Varga Synthesis (D1-D9)
    # We use Navamsha (D9) to refine the internal strength of the planet.
    navamsha_engine = NavamshaEngine()
    d9_sign = navamsha_engine.get_navamsha_sign(placement.sign, placement.degree)
    if d9_sign:
        # 5.1 Vargottama (Same sign in D1 and D9) - Classical big boost
        if d9_sign.lower() == placement.sign.lower():
            total_sthana += 45.0
            
        # 5.2 D9 Dignity Modifier (Lite Sapta-Vargiya)
        d9_dignity = DignityEngine.get_dignity(planet_id, d9_sign)
        if d9_dignity == "exalted":
            total_sthana += 30.0
        elif d9_dignity == "own":
            total_sthana += 15.0
        elif d9_dignity == "debilitated":
            # Significant reduction - "Hollow planet" logic
            total_sthana -= 30.0

    return max(0.0, total_sthana)
