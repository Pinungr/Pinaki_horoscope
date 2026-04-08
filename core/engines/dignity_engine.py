from __future__ import annotations
from typing import Dict, List

class DignityEngine:
    """
    Utility to determine planetary dignity (Exalted, Own, Debilitated, etc).
    """

    EXALTED_SIGNS = {
        "sun": "aries",
        "moon": "taurus",
        "mars": "capricorn",
        "mercury": "virgo",
        "jupiter": "cancer",
        "venus": "pisces",
        "saturn": "libra"
    }

    DEBILITATED_SIGNS = {
        "sun": "libra",
        "moon": "scorpio",
        "mars": "cancer",
        "mercury": "pisces",
        "jupiter": "capricorn",
        "venus": "virgo",
        "saturn": "aries"
    }

    OWN_SIGNS = {
        "sun": ["leo"],
        "moon": ["cancer"],
        "mars": ["aries", "scorpio"],
        "mercury": ["gemini", "virgo"],
        "jupiter": ["sagittarius", "pisces"],
        "venus": ["taurus", "libra"],
        "saturn": ["capricorn", "aquarius"]
    }

    @staticmethod
    def get_dignity(planet: str, sign: str) -> str:
        """
        Returns: 'exalted', 'own', 'debilitated', or 'neutral'.
        """
        planet = planet.lower().strip()
        sign = sign.lower().strip()

        if DignityEngine.EXALTED_SIGNS.get(planet) == sign:
            return "exalted"
        if DignityEngine.DEBILITATED_SIGNS.get(planet) == sign:
            return "debilitated"
        if sign in DignityEngine.OWN_SIGNS.get(planet, []):
            return "own"
        
        return "neutral"
