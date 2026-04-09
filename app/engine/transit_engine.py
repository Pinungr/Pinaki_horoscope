from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Dict, Any

import swisseph as swe
from core.yoga.models import ChartSnapshot

logger = logging.getLogger(__name__)

class TransitEngine:
    """
    Gochar (Transit) Engine.
    Calculates current planetary positions and maps them to Natal houses.
    """

    def __init__(self):
        self._zodiac_signs = [
            "aries", "taurus", "gemini", "cancer", 
            "leo", "virgo", "libra", "scorpio", 
            "sagittarius", "capricorn", "aquarius", "pisces"
        ]
        self._supportive_houses = {1, 2, 3, 5, 6, 9, 10, 11}
        self._challenging_houses = {4, 7, 8, 12}

    def calculate_transits(
        self, 
        natal_chart: ChartSnapshot, 
        target_time: datetime | None = None,
        reference: str = "moon",
    ) -> Dict[str, Any]:
        """
        Calculates transits for a given time relative to a natal reference point.
        reference: "moon" (Chandra Lagna), "lagna" (Ascendant), or "both".
        """
        if target_time is None:
            target_time = datetime.now(timezone.utc)

        normalized_reference = str(reference or "moon").strip().lower() or "moon"

        # Shared core transit computation (single Swiss Ephemeris pass).
        transit_positions = self._get_current_positions(target_time)

        if normalized_reference == "both":
            return self._build_dual_reference_payload(
                natal_chart=natal_chart,
                transit_positions=transit_positions,
                target_time=target_time,
            )

        reference_key = "moon" if normalized_reference == "moon" else "lagna"
        reference_view = self._build_reference_view(
            natal_chart=natal_chart,
            transit_positions=transit_positions,
            reference=reference_key,
        )

        return {
            "transits": reference_view,
            "reference": reference_key,
            "target_time": target_time.isoformat(),
        }

    def _build_dual_reference_payload(
        self,
        *,
        natal_chart: ChartSnapshot,
        transit_positions: Dict[str, dict],
        target_time: datetime,
    ) -> Dict[str, Any]:
        from_moon = self._build_reference_view(
            natal_chart=natal_chart,
            transit_positions=transit_positions,
            reference="moon",
        )
        from_lagna = self._build_reference_view(
            natal_chart=natal_chart,
            transit_positions=transit_positions,
            reference="lagna",
        )

        transit_matrix: Dict[str, Dict[str, Any]] = {}
        for planet, payload in transit_positions.items():
            p_long = float(payload["long"])
            p_sign_idx = int(p_long / 30)
            sign = self._zodiac_signs[p_sign_idx]
            is_retrograde = bool(payload["is_retrograde"])

            moon_row = from_moon.get(planet, {})
            lagna_row = from_lagna.get(planet, {})

            transit_matrix[planet] = {
                "transit_planet": planet,
                "sign": sign,
                "absolute_longitude": round(p_long, 4),
                "is_retrograde": is_retrograde,
                "from_lagna": {
                    "house_position": lagna_row.get("house_from_reference"),
                    "effects": lagna_row.get("effects", []),
                    "strength_modifiers": lagna_row.get("strength_modifiers", []),
                },
                "from_moon": {
                    "house_position": moon_row.get("house_from_reference"),
                    "effects": moon_row.get("effects", []),
                    "strength_modifiers": moon_row.get("strength_modifiers", []),
                },
            }

        return {
            # Backward-compatible surface (kept moon-first for existing consumers)
            "transits": from_moon,
            "reference": "both",
            "target_time": target_time.isoformat(),
            # Explicitly separated dual-reference views
            "from_lagna": from_lagna,
            "from_moon": from_moon,
            # Per-planet combined structure for downstream engines/UI
            "transit_matrix": transit_matrix,
        }

    def _build_reference_view(
        self,
        *,
        natal_chart: ChartSnapshot,
        transit_positions: Dict[str, dict],
        reference: str,
    ) -> Dict[str, Any]:
        ref_planet = "moon" if str(reference).strip().lower() == "moon" else "ascendant"
        natal_ref = natal_chart.get(ref_planet)

        if not natal_ref:
            logger.warning("Natal reference point '%s' not found for transit calculation.", ref_planet)
            return {}

        ref_sign = str(natal_ref.sign or "").strip().lower()
        if ref_sign not in self._zodiac_signs:
            logger.warning("Natal reference sign '%s' is invalid for transit calculation.", ref_sign)
            return {}
        ref_sign_idx = self._zodiac_signs.index(ref_sign)

        output: Dict[str, Dict[str, Any]] = {}
        for planet, payload in transit_positions.items():
            p_long = float(payload["long"])
            p_sign_idx = int(p_long / 30)
            relative_house = (p_sign_idx - ref_sign_idx) % 12 + 1
            is_retrograde = bool(payload["is_retrograde"])

            output[planet] = {
                "sign": self._zodiac_signs[p_sign_idx],
                "house_from_reference": relative_house,
                "absolute_longitude": round(p_long, 4),
                "is_retrograde": is_retrograde,
                "effects": self._derive_effects(
                    planet=planet,
                    house_position=relative_house,
                    reference=reference,
                ),
                "strength_modifiers": self._derive_strength_modifiers(
                    house_position=relative_house,
                    is_retrograde=is_retrograde,
                ),
            }

        return output

    def _derive_effects(self, *, planet: str, house_position: int, reference: str) -> list[str]:
        ref_label = "Lagna" if str(reference).strip().lower() == "lagna" else "Chandra Lagna"
        if house_position in self._supportive_houses:
            return [
                f"{planet.title()} transit is generally supportive from {ref_label} in house {house_position}."
            ]
        if house_position in self._challenging_houses:
            return [
                f"{planet.title()} transit may feel demanding from {ref_label} in house {house_position}."
            ]
        return [
            f"{planet.title()} transit gives mixed outcomes from {ref_label} in house {house_position}."
        ]

    def _derive_strength_modifiers(self, *, house_position: int, is_retrograde: bool) -> list[str]:
        modifiers: list[str] = []
        if house_position in self._supportive_houses:
            modifiers.append("supportive_house_context")
        elif house_position in self._challenging_houses:
            modifiers.append("challenging_house_context")
        else:
            modifiers.append("neutral_house_context")

        if house_position in {1, 5, 9}:
            modifiers.append("trikona_emphasis")
        if house_position in {6, 8, 12}:
            modifiers.append("dusthana_intensity")
        modifiers.append("retrograde" if is_retrograde else "direct_motion")
        return modifiers

    def _get_current_positions(self, target_time: datetime) -> Dict[str, dict]:
        """Calculates geocentric sidereal longitudes and motional status."""
        jd_ut = swe.julday(
            target_time.year, target_time.month, target_time.day,
            target_time.hour + target_time.minute / 60.0 + target_time.second / 3600.0
        )
        
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL
        
        planets = {
            "sun": swe.SUN, "moon": swe.MOON, "mars": swe.MARS, 
            "mercury": swe.MERCURY, "jupiter": swe.JUPITER, 
            "venus": swe.VENUS, "saturn": swe.SATURN, "rahu": swe.MEAN_NODE
        }
        
        results = {}
        for name, p_idx in planets.items():
            res, _ = swe.calc_ut(jd_ut, p_idx, flags)
            results[name] = {"long": res[0], "is_retrograde": res[3] < 0}
            
            if name == "rahu":
                results["ketu"] = {"long": (res[0] + 180.0) % 360.0, "is_retrograde": res[3] < 0}
                
        return results
