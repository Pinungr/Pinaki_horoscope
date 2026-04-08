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
    Calculates Vedic-style dignitary strength for every planet in a chart.

    Usage
    -----
    ::

        engine = StrengthEngine()
        results = engine.score_chart(chart_snapshot)
        sun_strength = engine.score_planet("sun", chart_snapshot)
        print(sun_strength.score, sun_strength.level)
    """

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def score_chart(self, chart: ChartSnapshot) -> dict[str, PlanetStrength]:
        """
        Returns a strength assessment for every planet present in the chart.

        Returns
        -------
        dict mapping normalized planet id -> PlanetStrength
        """
        results: dict[str, PlanetStrength] = {}
        for planet_id in chart.placements:
            results[planet_id] = self.score_planet(planet_id, chart)
        return results

    def score_planet(self, planet: str, chart: ChartSnapshot) -> PlanetStrength:
        """
        Scores a single planet against the full chart context.

        Parameters
        ----------
        planet  : planet name (any casing; will be normalized)
        chart   : ChartSnapshot with all placements
        """
        planet_id = normalize_planet_id(planet)
        placement = chart.get(planet_id)

        if placement is None:
            logger.debug("StrengthEngine: planet %r not found in chart.", planet_id)
            return PlanetStrength(planet=planet_id, score=0, level="weak", breakdown={})

        breakdown: dict[str, int] = {"base": _BASE_SCORE}
        total = _BASE_SCORE

        total = self._apply_dignity(planet_id, placement, breakdown, total)
        total = self._apply_retrograde(placement, breakdown, total)
        total = self._apply_combustion(planet_id, placement, chart, breakdown, total)
        total = self._apply_house_strength(placement, breakdown, total)

        clamped = max(0, min(100, total))
        level = self._level_for_score(clamped)

        logger.debug(
            "StrengthEngine: %s score=%d level=%s breakdown=%s",
            planet_id,
            clamped,
            level,
            breakdown,
        )

        return PlanetStrength(
            planet=planet_id,
            score=clamped,
            level=level,
            breakdown=breakdown,
        )

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
        if placement.retrograde:
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

        # Combustion is only possible when both are in the same sign (same house
        # in whole-sign system), or adjacent signs with degree proximity.
        # We use a simple degree-delta check: compute the absolute arc on the
        # ecliptic between the two planets using their within-sign degrees.
        # Full absolute longitude comparison would require storing it; we
        # approximate using house proximity + degree delta.
        if sun.house != placement.house:
            return total

        degree_delta = abs(sun.degree - placement.degree)
        if degree_delta <= orb:
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
