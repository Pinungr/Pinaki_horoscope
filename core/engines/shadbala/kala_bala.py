from __future__ import annotations
from typing import Dict
from core.yoga.models import ChartSnapshot, PlanetPlacement, normalize_planet_id

def calculate_kala_bala(planet: str, placement: PlanetPlacement, sun_placement: PlanetPlacement) -> float:
    """
    Calculates Temporal Strength (Kala Bala).
    MVP Version: Includes Dina-Ratri Bala (Day/Night strength).
    
    Day: Sun is in houses 7, 8, 9, 10, 11, 12.
    Night: Sun is in houses 1, 2, 3, 4, 5, 6.
    """
    planet_id = normalize_planet_id(planet)
    is_day = sun_placement.house >= 7
    
    total_kala = 0.0
    
    # 1. Dina-Ratri Bala (60 Virupas for compatible planets)
    if is_day:
        # Sun, Jupiter, Venus are strong in the Day
        if planet_id in {"sun", "jupiter", "venus"}:
            total_kala += 60.0
    else:
        # Moon, Mars, Saturn are strong in the Night
        if planet_id in {"moon", "mars", "saturn"}:
            total_kala += 60.0
            
    # Mercury is always strong (some schools give 60, some give it at sunrise/sunset)
    if planet_id == "mercury":
        total_kala += 60.0
        
    return total_kala
