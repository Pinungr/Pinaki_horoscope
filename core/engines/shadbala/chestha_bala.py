from __future__ import annotations
from core.yoga.models import PlanetPlacement, normalize_planet_id

def calculate_chestha_bala(planet: str, placement: PlanetPlacement) -> float:
    """
    Calculates Motional Strength (Chestha Bala).
    MVP: Gives 60 Virupas if planet is retrograde.
    (Classical rules are more complex, involving velocity and house orientation).
    """
    planet_id = normalize_planet_id(planet)
    
    # Sun and Moon represent velocity-based chestha bala; for MVP we return a base 30.
    if planet_id in {"sun", "moon"}:
        return 30.0
    
    # Rahu and Ketu are always retrograde; return 30 base.
    if planet_id in {"rahu", "ketu"}:
        return 30.0
    
    if placement.is_retrograde:
        return 60.0
    
    return 0.0
