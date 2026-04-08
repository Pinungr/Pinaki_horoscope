from __future__ import annotations

"""
Planetary Strength Engine
=========================
Scores a planet's strength on a 0-100 scale using classical Vedic criteria:

  Factor              Max pts   Notes
  -------------------------------------------------------------
  Exaltation          +30       Highest dignity
  Own sign            +20       Planet in its own sign
  Debilitation        -25       Weakest placement (can go negative -> floored)
  Retrograde          +10       Classical strength boost for retrograde planets
  Combustion          -15       Too close to Sun (within orb)
  House strength      +15       Angular (kendra) or trine (trikona) houses
  -------------------------------------------------------------
  Neutral base          50      All planets start here

Thresholds
----------
  score >= 70  -> "strong"
  score >= 40  -> "medium"
  score <  40  -> "weak"
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from core.yoga.models import ChartSnapshot, PlanetPlacement, normalize_planet_id
from .shadbala.shadbala_aggregator import ShadbalaEngine, ShadbalaResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Classical dignity tables (lowercase planet keys)
# ---------------------------------------------------------------------------

EXALTATION_SIGNS: dict[str, str] = {
    "sun": "aries",
    "moon": "taurus",
    "mars": "capricorn",
    "mercury": "virgo",
    "jupiter": "cancer",
    "venus": "pisces",
    "saturn": "libra",
    "rahu": "gemini",
    "ketu": "sagittarius",
}

DEBILITATION_SIGNS: dict[str, str] = {
    "sun": "libra",
    "moon": "scorpio",
    "mars": "cancer",
    "mercury": "pisces",
    "jupiter": "capricorn",
    "venus": "virgo",
    "saturn": "aries",
    "rahu": "sagittarius",
    "ketu": "gemini",
}

OWN_SIGNS: dict[str, tuple[str, ...]] = {
    "sun": ("leo",),
    "moon": ("cancer",),
    "mars": ("aries", "scorpio"),
    "mercury": ("gemini", "virgo"),
    "jupiter": ("sagittarius", "pisces"),
    "venus": ("taurus", "libra"),
    "saturn": ("capricorn", "aquarius"),
    "rahu": (),
    "ketu": (),
}

# Combustion orb in degrees (planet must be within this of the Sun)
COMBUSTION_ORB: dict[str, float] = {
    "moon": 12.0,
    "mars": 17.0,
    "mercury": 14.0,  # when not retrograde; retrograde orb is 12 deg (simplified)
    "jupiter": 11.0,
    "venus": 10.0,
    "saturn": 15.0,
}

# Angular (kendra) and trine (trikona) houses grant extra strength
KENDRA_HOUSES: frozenset[int] = frozenset({1, 4, 7, 10})
TRIKONA_HOUSES: frozenset[int] = frozenset({1, 5, 9})

# Scoring weights
_BASE_SCORE = 50
_EXALTATION_BONUS = 30
_OWN_SIGN_BONUS = 20
_DEBILITATION_PENALTY = -25
_RETROGRADE_BONUS = 10
_COMBUSTION_PENALTY = -15
_KENDRA_BONUS = 15
_TRIKONA_BONUS = 10  # 1st house is both kendra and trikona; apply the higher bonus


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlanetStrength:
    """
    Strength assessment for a single planet.

    Attributes
    ----------
    planet      : normalized planet id (lowercase)
    score       : clamped integer 0-100
    level       : "weak" | "medium" | "strong"
    breakdown   : per-factor contribution for debugging / logging
    """

    planet: str
    score: int
    level: str
    breakdown: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "planet": self.planet,
            "score": self.score,
            "level": self.level,
            "breakdown": dict(self.breakdown),
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class StrengthEngine:
    """
    Calculates planetary strength using the modular Shadbala (Six-Fold) system.
    Maintains backward compatibility with 0-100 scoring while providing
    professional-grade astronomical precision.
    """

    def __init__(self):
        self._shadbala_engine = ShadbalaEngine()

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def score_chart(self, chart: ChartSnapshot) -> dict[str, PlanetStrength]:
        """
        Returns a strength assessment for every planet present in the chart.
        Uses Shadbala for high-precision results.
        """
        shadbala_result = self._shadbala_engine.calculate(chart)
        results: dict[str, PlanetStrength] = {}
        
        for planet_id, sb in shadbala_result.planets.items():
            score = self._to_percentage(sb.total, planet_id)
            level = self._level_for_score(score)
            
            # Map Shadbala factors back to the breakdown for UI compatibility
            breakdown = {
                "sthana": round(sb.sthana_bala, 1),
                "dik": round(sb.dik_bala, 1),
                "kala": round(sb.kala_bala, 1),
                "chestha": round(sb.chestha_bala, 1),
                "naisargika": round(sb.naisargika_bala, 1),
                "total_virupas": round(sb.total, 1)
            }
            
            results[planet_id] = PlanetStrength(
                planet=planet_id,
                score=score,
                level=level,
                breakdown=breakdown
            )
            
        return results

    def score_planet(self, planet: str, chart: ChartSnapshot) -> PlanetStrength:
        """Scores a single planet against the full chart context."""
        planet_id = normalize_planet_id(planet)
        all_results = self.score_chart(chart)
        return all_results.get(planet_id, PlanetStrength(planet=planet_id, score=0, level="weak", breakdown={}))

    @staticmethod
    def _to_percentage(total_virupas: float, planet: str) -> int:
        """
        Maps raw Shadbala Virupa points to a 0-100 percentage.
        Standard 'Strong' thresholds (Minimum Required Virupas):
        Sun: 390, Moon: 360, Mars: 300, Mercury: 420, Jupiter: 390, Venus: 330, Saturn: 300
        """
        thresholds = {
            "sun": 390, "moon": 360, "mars": 300, 
            "mercury": 420, "jupiter": 390, "venus": 330, "saturn": 300
        }
        
        target = thresholds.get(planet, 300)
        # Scaled so that reaching the threshold is roughly 75/100
        percentage = (total_virupas / target) * 75
        return int(round(max(0, min(100, percentage))))

    # -----------------------------------------------------------------------
    # Factor handlers
    # -----------------------------------------------------------------------

    @staticmethod
    def _apply_dignity(
        planet_id: str,
        placement: PlanetPlacement,
        breakdown: dict[str, int],
        total: int,
    ) -> int:
        sign = str(placement.sign or "").strip().lower()

        if sign and sign == EXALTATION_SIGNS.get(planet_id):
            breakdown["exaltation"] = _EXALTATION_BONUS
            return total + _EXALTATION_BONUS

        if sign and sign == DEBILITATION_SIGNS.get(planet_id):
            breakdown["debilitation"] = _DEBILITATION_PENALTY
            return total + _DEBILITATION_PENALTY

        if sign and sign in OWN_SIGNS.get(planet_id, ()):
            breakdown["own_sign"] = _OWN_SIGN_BONUS
            return total + _OWN_SIGN_BONUS

        return total

    @staticmethod
    def _apply_retrograde(
        placement: PlanetPlacement,
        breakdown: dict[str, int],
        total: int,
    ) -> int:
        if placement.is_retrograde:
            breakdown["retrograde"] = _RETROGRADE_BONUS
            return total + _RETROGRADE_BONUS
        return total

    @staticmethod
    def _apply_combustion(
        planet_id: str,
        placement: PlanetPlacement,
        chart: ChartSnapshot,
        breakdown: dict[str, int],
        total: int,
    ) -> int:
        """Applies combustion penalty when a planet is within orb of the Sun."""
        if planet_id == "sun":
            return total

        orb = COMBUSTION_ORB.get(planet_id)
        if orb is None:
            # Rahu / Ketu are not combusted by classical rules
            return total

        sun = chart.get("sun")
        if sun is None:
            return total

        # Combustion orb check using precise absolute longitude proximity.
        # Calculate the shortest distance on a 360-degree circle.
        delta = abs(sun.absolute_longitude - placement.absolute_longitude)
        shortest_arc = min(delta, 360.0 - delta)

        if shortest_arc <= orb:
            breakdown["combustion"] = _COMBUSTION_PENALTY
            return total + _COMBUSTION_PENALTY

        return total

    @staticmethod
    def _apply_house_strength(
        placement: PlanetPlacement,
        breakdown: dict[str, int],
        total: int,
    ) -> int:
        house = placement.house
        if house in KENDRA_HOUSES and house in TRIKONA_HOUSES:
            # House 1 is both; grant the higher bonus.
            breakdown["kendra_trikona"] = _KENDRA_BONUS
            return total + _KENDRA_BONUS
        if house in KENDRA_HOUSES:
            breakdown["kendra"] = _KENDRA_BONUS
            return total + _KENDRA_BONUS
        if house in TRIKONA_HOUSES:
            breakdown["trikona"] = _TRIKONA_BONUS
            return total + _TRIKONA_BONUS
        return total

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _level_for_score(score: int) -> str:
        if score >= 70:
            return "strong"
        if score >= 40:
            return "medium"
        return "weak"
