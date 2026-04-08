from __future__ import annotations
from typing import Dict, Set, List

class FunctionalNatureEngine:
    """
    Classifies planets as Benefic, Malefic, or Yogakaraka 
    relative to the Ascendant (Lagna).
    """

    def __init__(self):
        self._rulerships = {
            "aries": ["mars"],
            "taurus": ["venus"],
            "gemini": ["mercury"],
            "cancer": ["moon"],
            "leo": ["sun"],
            "virgo": ["mercury"],
            "libra": ["venus"],
            "scorpio": ["mars"],
            "sagittarius": ["jupiter"],
            "capricorn": ["saturn"],
            "aquarius": ["saturn"],
            "pisces": ["jupiter"]
        }
        self._zodiac = [
            "aries", "taurus", "gemini", "cancer", "leo", "virgo",
            "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces"
        ]

    def get_planet_roles(self, lagna_sign: str) -> Dict[str, str]:
        """
        Determines the role of each planet for the given Lagna.
        Returns: { 'jupiter': 'malefic', 'saturn': 'yogakaraka', ... }
        """
        lagna_sign = lagna_sign.lower().strip()
        if lagna_sign not in self._zodiac:
            return {}

        lagna_idx = self._zodiac.index(lagna_sign)
        
        # 1. Map House Index -> PlanetID
        house_lords: Dict[int, List[str]] = {}
        lord_to_houses: Dict[str, Set[int]] = {p: set() for p in [
            "sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn"
        ]}

        for house_num in range(1, 13):
            sign_idx = (lagna_idx + house_num - 1) % 12
            sign_name = self._zodiac[sign_idx]
            lords = self._rulerships[sign_name]
            house_lords[house_num] = lords
            for l in lords:
                lord_to_houses[l].add(house_num)

        # 2. Classify Lords
        roles = {}
        for planet, houses in lord_to_houses.items():
            # Trikonas: 1, 5, 9
            # Kendras: 1, 4, 7, 10
            # Dusthanas: 6, 8, 12
            
            is_trikona_lord = any(h in {1, 5, 9} for h in houses)
            is_kendra_lord = any(h in {1, 4, 7, 10} for h in houses)
            is_dusthana_lord = any(h in {6, 8, 12} for h in houses)
            
            # Special case: Yogakaraka (Kendra + Trikona)
            if is_kendra_lord and is_trikona_lord and planet not in {"sun", "moon"}:
                roles[planet] = "yogakaraka"
            elif planet in {"sun", "moon"} and (is_kendra_lord or is_trikona_lord):
                # Sun/Moon are usually treated as benefics if they rule any pillar
                roles[planet] = "benefic"
            elif is_trikona_lord:
                roles[planet] = "benefic"
            elif is_dusthana_lord and not is_kendra_lord:
                roles[planet] = "malefic"
            else:
                roles[planet] = "neutral"

        return roles
