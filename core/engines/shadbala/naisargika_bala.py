from __future__ import annotations
from typing import Dict
from core.yoga.models import normalize_planet_id

# Natural Strength (Naisargika Bala)
# Saturn < Mars < Mercury < Jupiter < Venus < Moon < Sun
NAISARGIKA_BALA: Dict[str, float] = {
    "saturn": 8.57,
    "mars": 17.14,
    "mercury": 25.71,
    "jupiter": 34.28,
    "venus": 42.85,
    "moon": 51.42,
    "sun": 60.00,
    "rahu": 0.0,
    "ketu": 0.0,
}

def calculate_naisargika_bala(planet: str) -> float:
    """Returns the fixed natural strength of a planet in Virupas."""
    return NAISARGIKA_BALA.get(normalize_planet_id(planet), 0.0)
