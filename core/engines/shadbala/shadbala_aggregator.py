from __future__ import annotations
import logging
from typing import Dict

from core.yoga.models import ChartSnapshot, normalize_planet_id
from .shadbala_models import PlanetShadbala, ShadbalaResult
from .sthana_bala import calculate_sthana_bala
from .dik_bala import calculate_dik_bala
from .naisargika_bala import calculate_naisargika_bala
from .kala_bala import calculate_kala_bala
from .chestha_bala import calculate_chestha_bala
from .drik_bala import DrikBalaCalculator
from app.engine.navamsha import NavamshaEngine

logger = logging.getLogger(__name__)

class ShadbalaEngine:
    """
    The master engine for Six-Fold Planetary Strength (Shadbala).
    Aggregates positional, directional, temporal, motional, natural, and aspectual strengths.
    """

    def __init__(self):
        self.navamsha_engine = NavamshaEngine()

    def calculate(self, chart: ChartSnapshot) -> ShadbalaResult:
        """Calculates total Shadbala for all planets in the chart."""
        result = ShadbalaResult()
        drik_calc = DrikBalaCalculator()
        
        sun_placement = chart.get("sun")
        asc_placement = chart.get("ascendant") or chart.get("lagna")
        
        logger.debug("Shadbala calculation: Sun=%s, Ascendant=%s", sun_placement is not None, asc_placement is not None)
        if not sun_placement or not asc_placement:
            logger.warning("Shadbala calculation requires Sun and Ascendant placements. Found keys: %s", list(chart.placements.keys()))
            return result

        for planet_id, placement in chart.placements.items():
            if planet_id == "ascendant":
                continue
                
            # 1. Sthana Bala
            sthana = calculate_sthana_bala(planet_id, placement, sun_placement)
            
            # 2. Dik Bala
            dik = calculate_dik_bala(planet_id, placement, asc_placement.absolute_longitude)
            
            # 3. Naisargika Bala
            naisargika = calculate_naisargika_bala(planet_id)
            
            # 4. Kala Bala
            kala = calculate_kala_bala(planet_id, placement, sun_placement)
            
            # 5. Chestha Bala
            chestha = calculate_chestha_bala(planet_id, placement)
            
            # 6. Drik Bala
            drik = drik_calc.calculate(planet_id, chart)
            
            # Vargottama detection using high-precision instance
            d9_sign = self.navamsha_engine.get_navamsha_sign(placement.sign, placement.degree)
            vargottama = (d9_sign.lower() == placement.sign.lower()) if d9_sign else False
            
            result.planets[planet_id] = PlanetShadbala(
                planet=planet_id,
                sthana_bala=sthana,
                dik_bala=dik,
                kala_bala=kala,
                chestha_bala=chestha,
                naisargika_bala=naisargika,
                drik_bala=drik,
                is_vargottama=vargottama
            )
            
        return result
