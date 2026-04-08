from __future__ import annotations
from typing import Dict
from core.yoga.models import ChartSnapshot, PlanetPlacement, normalize_planet_id

class DrikBalaCalculator:
    """
    Calculates Drik Bala (Aspectual Strength).
    A planet gains strength from aspects of benefics and loses from malefics.
    """

    def __init__(self):
        self._benefics = {"jupiter", "venus", "mercury"}
        self._malefics = {"saturn", "mars", "sun"}

    def calculate(self, planet_id: str, chart: ChartSnapshot) -> float:
        """Calculates total Drik Bala for a specific planet."""
        target_p = chart.get(planet_id)
        if not target_p:
            return 0.0

        total_drik = 0.0
        for source_id, source_p in chart.placements.items():
            if source_id == planet_id or source_id == "ascendant":
                continue
            
            drishti_value = self._get_drishti_value(source_id, source_p, target_p)
            if drishti_value > 0:
                # If source is benefic, add to strength. If malefic, subtract.
                # In classical Shadbala, it's (Aspect of Benefic - Aspect of Malefic) / 4.
                # Here we use a scaled version for the 0-100 UI.
                if source_id in self._benefics:
                    total_drik += drishti_value
                elif source_id in self._malefics:
                    total_drik -= drishti_value

        # Typically divided by 4 in classical texts to get Virupas
        return total_drik / 4.0

    def _get_drishti_value(self, source_id: str, source: PlanetPlacement, target: PlanetPlacement) -> float:
        """Determines the Drishti (Aspect) value from source to target in Virupas (0-60)."""
        # Geocentric distance in degrees (0-360)
        diff = (target.absolute_longitude - source.absolute_longitude) % 360
        
        # 1. Universal 7th house aspect (180 +/- orb)
        if 170 <= diff <= 190:
            return 60.0
            
        # 2. Special Aspects
        if source_id == "jupiter":
            # 5th (120) and 9th (240)
            if (110 <= diff <= 130) or (230 <= diff <= 250):
                return 60.0
        elif source_id == "mars":
            # 4th (90) and 8th (210)
            if (80 <= diff <= 100) or (200 <= diff <= 220):
                return 60.0
        elif source_id == "saturn":
            # 3rd (60) and 10th (270)
            if (50 <= diff <= 70) or (260 <= diff <= 280):
                return 60.0
                
        # 3. Partial aspects (Simplified for MVP)
        # 3/4 aspect: 90/270 for non-saturn; 1/2 aspect: 120/240 for non-jupiter
        return 0.0
