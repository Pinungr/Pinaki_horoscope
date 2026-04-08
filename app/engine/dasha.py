from datetime import datetime, timedelta, timezone
import logging
from typing import List, Dict
from app.utils.logger import log_calculation_step


logger = logging.getLogger(__name__)

class DashaEngine:
    """Calculates Vimshottari Mahadasha progression based on Moon's longitude."""

    def __init__(self):
        # The exact order of Vimshottari Dasha Lords and their durations (years)
        self.dasha_sequence = [
            ("Ketu", 7),
            ("Venus", 20),
            ("Sun", 6),
            ("Moon", 10),
            ("Mars", 7),
            ("Rahu", 18),
            ("Jupiter", 16),
            ("Saturn", 19),
            ("Mercury", 17)
        ]
        
        self.NAKSHATRA_ARC = 360.0 / 27.0  # 13 degrees 20 minutes = 13.33333...
        self._total_years = sum(d for _, d in self.dasha_sequence)  # 120

    def calculate_dasha(self, moon_longitude: float, dob: str) -> List[Dict[str, str]]:
        """
        Calculates the Vimshottari Dasha timeline.
        dob format: 'YYYY-MM-DD'
        Returns list of sequential dicts: [{"planet": "Sun", "start": "2020-01-01", "end": "2026-01-01"}, ...]
        """
        log_calculation_step("dasha_calculation_started", moon_longitude=moon_longitude, dob=dob)
        if float(moon_longitude) < 0 or float(moon_longitude) >= 360:
            moon_longitude = moon_longitude % 360.0
            
        # 1. Determine Nakshatra index (0 to 26)
        nakshatra_idx = int(moon_longitude / self.NAKSHATRA_ARC)
        
        # 2. Identify the starting Dasha block (repeats every 9)
        start_dasha_idx = nakshatra_idx % 9
        
        # 3. Calculate how far the Moon has traveled through the current Nakshatra
        degrees_passed = moon_longitude % self.NAKSHATRA_ARC
        fraction_passed = degrees_passed / self.NAKSHATRA_ARC
        fraction_remaining = 1.0 - fraction_passed
        
        # 4. Starting planet and balance of duration at birth
        start_planet, total_years = self.dasha_sequence[start_dasha_idx]
        balance_years = total_years * fraction_remaining
        
        try:
            current_date = datetime.strptime(dob, "%Y-%m-%d")
        except ValueError:
            logger.warning("Invalid DOB '%s' received for dasha calculation. Falling back to UTC now.", dob)
            current_date = datetime.now(timezone.utc).replace(tzinfo=None)  # UTC fallback (naive for consistency)
            
        timeline = []
        
        # Push the balance dasha first
        end_date = current_date + timedelta(days=balance_years * 365.2425)
        timeline.append({
            "planet": start_planet,
            "start": current_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d")
        })
        log_calculation_step("dasha_period_computed", planet=start_planet, start=timeline[-1]["start"], end=timeline[-1]["end"])
        current_date = end_date
        
        # 5. Populate the remainder of the 120-year lifespan cycle
        current_idx = (start_dasha_idx + 1) % 9
        # 8 more dashas guarantees full 120 year coverage from birth
        for _ in range(8):
            planet, duration_years = self.dasha_sequence[current_idx]
            end_date = current_date + timedelta(days=duration_years * 365.2425)
            timeline.append({
                "planet": planet,
                "start": current_date.strftime("%Y-%m-%d"),
                "end": end_date.strftime("%Y-%m-%d")
            })
            log_calculation_step("dasha_period_computed", planet=planet, start=timeline[-1]["start"], end=timeline[-1]["end"])
            current_date = end_date
            current_idx = (current_idx + 1) % 9
            
        log_calculation_step("dasha_calculation_completed", periods=len(timeline))
        return timeline

    def calculate_dasha_with_antardashas(
        self, moon_longitude: float, dob: str
    ) -> List[Dict]:
        """
        Calculates the full Vimshottari Dasha timeline INCLUDING Antardasha
        (sub-period) breakdowns for every Mahadasha block.

        Each returned element contains a ``sub_periods`` list:

            {
                "planet": "Jupiter",
                "start": "2023-01-01",
                "end": "2039-01-01",
                "sub_periods": [
                    {"planet": "Jupiter", "antardasha": "Jupiter",
                     "start": "2023-01-01", "end": "2025-04-12"},
                    ...
                ]
            }

        Classical rule: duration of antardasha for planet B inside Mahadasha
        of planet A  =  (maha_duration_days * vimshottari_years_B / 120).
        """
        mahadashas = self.calculate_dasha(moon_longitude, dob)

        planet_years: Dict[str, int] = {p: y for p, y in self.dasha_sequence}
        sequence_names = [p for p, _ in self.dasha_sequence]

        result: List[Dict] = []
        for maha in mahadashas:
            maha_planet = maha["planet"]
            maha_start = datetime.strptime(maha["start"], "%Y-%m-%d")
            maha_end = datetime.strptime(maha["end"], "%Y-%m-%d")
            maha_duration_days = (maha_end - maha_start).days

            try:
                antar_start_idx = sequence_names.index(maha_planet)
            except ValueError:
                result.append(maha)
                continue

            sub_periods: List[Dict] = []
            antar_current = maha_start
            for offset in range(9):
                antar_idx = (antar_start_idx + offset) % 9
                antar_planet, antar_vimshottari = self.dasha_sequence[antar_idx]

                fraction = antar_vimshottari / self._total_years
                antar_days = maha_duration_days * fraction
                antar_end = antar_current + timedelta(days=antar_days)

                # Clamp last sub-period to Mahadasha boundary
                if offset == 8 or antar_end > maha_end:
                    antar_end = maha_end

                sub_periods.append({
                    "planet": maha_planet,
                    "antardasha": antar_planet,
                    "start": antar_current.strftime("%Y-%m-%d"),
                    "end": antar_end.strftime("%Y-%m-%d"),
                })
                antar_current = antar_end
                if antar_current >= maha_end:
                    break

            result.append({**maha, "sub_periods": sub_periods})

        log_calculation_step(
            "dasha_antardasha_completed",
            mahadashas=len(result),
            total_antardashas=sum(len(m.get("sub_periods", [])) for m in result),
        )
        return result

