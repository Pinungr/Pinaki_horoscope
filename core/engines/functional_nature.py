from __future__ import annotations

from typing import Any, Dict, Set

_ZODIAC_SIGNS: tuple[str, ...] = (
    "aries",
    "taurus",
    "gemini",
    "cancer",
    "leo",
    "virgo",
    "libra",
    "scorpio",
    "sagittarius",
    "capricorn",
    "aquarius",
    "pisces",
)

_SIGN_LORDS: dict[str, str] = {
    "aries": "mars",
    "taurus": "venus",
    "gemini": "mercury",
    "cancer": "moon",
    "leo": "sun",
    "virgo": "mercury",
    "libra": "venus",
    "scorpio": "mars",
    "sagittarius": "jupiter",
    "capricorn": "saturn",
    "aquarius": "saturn",
    "pisces": "jupiter",
}

_CLASSICAL_PLANETS: tuple[str, ...] = (
    "sun",
    "moon",
    "mars",
    "mercury",
    "jupiter",
    "venus",
    "saturn",
)

_TRIKONA_HOUSES: frozenset[int] = frozenset({5, 9})
_KENDRA_HOUSES: frozenset[int] = frozenset({1, 4, 7, 10})
_YOGAKARAKA_KENDRA_HOUSES: frozenset[int] = frozenset({4, 7, 10})
_DUSTHANA_HOUSES: frozenset[int] = frozenset({6, 8, 12})
_UPACHAYA_MALEFIC_HOUSES: frozenset[int] = frozenset({3, 11})
_MARAKA_HOUSES: frozenset[int] = frozenset({2, 7})


class FunctionalNatureEngine:
    """
    Classifies functional planet roles based on Lagna-derived house ownership.

    Roles:
    - benefic
    - malefic
    - yogakaraka
    - neutral
    """

    def get_functional_nature(self, lagna: str, planet: str) -> str:
        """Returns one role for one planet for a given Lagna sign."""
        normalized_planet = str(planet or "").strip().lower()
        if normalized_planet not in _CLASSICAL_PLANETS:
            return "neutral"
        return self.get_planet_roles(lagna).get(normalized_planet, "neutral")

    def get_planet_roles(self, lagna_sign: str) -> Dict[str, str]:
        """
        Backward-compatible role map:
        { "jupiter": "benefic", "saturn": "malefic", ... }
        """
        return self.get_functional_profile(lagna_sign).get("roles", {})

    def get_functional_profile(self, lagna_sign: str) -> Dict[str, Any]:
        """
        Returns a structured Lagna-based functional nature matrix for downstream engines.
        """
        normalized_lagna = str(lagna_sign or "").strip().lower()
        if normalized_lagna not in _ZODIAC_SIGNS:
            return {
                "lagna": normalized_lagna,
                "house_lords": {},
                "planet_houses": {planet: [] for planet in _CLASSICAL_PLANETS},
                "roles": {planet: "neutral" for planet in _CLASSICAL_PLANETS},
                "benefics": [],
                "malefics": [],
                "yogakarakas": [],
                "neutrals": list(_CLASSICAL_PLANETS),
            }

        house_lords = self._compute_house_lords(normalized_lagna)
        planet_houses = self._invert_house_lords(house_lords)
        roles = {
            planet: self._classify_planet(planet_houses.get(planet, set()))
            for planet in _CLASSICAL_PLANETS
        }

        return {
            "lagna": normalized_lagna,
            "house_lords": house_lords,
            "planet_houses": {
                planet: sorted(planet_houses.get(planet, set()))
                for planet in _CLASSICAL_PLANETS
            },
            "roles": roles,
            "benefics": sorted([planet for planet, role in roles.items() if role == "benefic"]),
            "malefics": sorted([planet for planet, role in roles.items() if role == "malefic"]),
            "yogakarakas": sorted([planet for planet, role in roles.items() if role == "yogakaraka"]),
            "neutrals": sorted([planet for planet, role in roles.items() if role == "neutral"]),
        }

    @staticmethod
    def _compute_house_lords(lagna_sign: str) -> Dict[int, str]:
        lagna_index = _ZODIAC_SIGNS.index(lagna_sign)
        house_lords: Dict[int, str] = {}

        for house_num in range(1, 13):
            sign_index = (lagna_index + house_num - 1) % 12
            house_sign = _ZODIAC_SIGNS[sign_index]
            house_lords[house_num] = _SIGN_LORDS[house_sign]

        return house_lords

    @staticmethod
    def _invert_house_lords(house_lords: Dict[int, str]) -> Dict[str, Set[int]]:
        planet_houses: Dict[str, Set[int]] = {planet: set() for planet in _CLASSICAL_PLANETS}
        for house_num, planet in house_lords.items():
            if planet in planet_houses:
                planet_houses[planet].add(house_num)
        return planet_houses

    @staticmethod
    def _classify_planet(houses: Set[int]) -> str:
        if not houses:
            return "neutral"

        owns_trikona = bool(houses & _TRIKONA_HOUSES)
        owns_kendra_for_yoga = bool(houses & _YOGAKARAKA_KENDRA_HOUSES)
        if owns_trikona and owns_kendra_for_yoga:
            return "yogakaraka"

        benefic_score = 0.0
        malefic_score = 0.0

        for house in houses:
            if house in _TRIKONA_HOUSES:
                benefic_score += 3.0
            elif house == 1:
                benefic_score += 2.0
            elif house in {4, 10}:
                benefic_score += 1.0
            elif house == 7:
                benefic_score += 0.5

            if house in _DUSTHANA_HOUSES:
                malefic_score += 2.0
            elif house in _UPACHAYA_MALEFIC_HOUSES:
                malefic_score += 2.0

            if house in _MARAKA_HOUSES:
                malefic_score += 1.0

        if benefic_score - malefic_score >= 1.0:
            return "benefic"
        if malefic_score - benefic_score >= 1.0:
            return "malefic"
        return "neutral"


_default_engine = FunctionalNatureEngine()


def get_functional_nature(lagna: str, planet: str) -> str:
    """Convenience function for direct functional role lookup."""
    return _default_engine.get_functional_nature(lagna, planet)
