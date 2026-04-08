from __future__ import annotations
from typing import Dict
from core.yoga.models import PlanetPlacement, normalize_planet_id

# Directional Strength (Dik Bala) targets
# Planet -> Optimal House
DIK_BALA_TARGETS: Dict[str, int] = {
    "jupiter": 1,
    "mercury": 1,
    "sun": 10,
    "mars": 10,
    "saturn": 7,
    "moon": 4,
    "venus": 4,
}

def calculate_dik_bala(planet: str, placement: PlanetPlacement, ascendant_long: float) -> float:
    """
    Calculates Directional Strength (Dik Bala).
    Simplified: Uses distance from preferred house cusps assuming Whole-Sign/Equal.
    
    Jupiter/Mercury: 60 at 1st House cusp (Ascendant).
    Sun/Mars: 60 at 10th House cusp.
    Saturn: 60 at 7th House cusp.
    Moon/Venus: 60 at 4th House cusp.
    """
    planet_id = normalize_planet_id(planet)
    if planet_id not in DIK_BALA_TARGETS:
        return 0.0
    
    target_house = DIK_BALA_TARGETS[planet_id]
    
    # Calculate target longitude
    # 1st: asc, 4th: asc+90, 7th: asc+180, 10th: asc+270
    target_long = (ascendant_long + (target_house - 1) * 30.0) % 360.0
    
    # Loss point is 180 degrees from target
    loss_point = (target_long + 180.0) % 360.0
    
    # Distance from loss point (0 at loss point, 180 at target)
    diff = (placement.absolute_longitude - loss_point) % 360.0
    
    # Dik Bala = diff / 3 (since 180 / 3 = 60)
    return diff / 3.0
