from datetime import datetime, timedelta
from typing import List, Dict

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

    def calculate_dasha(self, moon_longitude: float, dob: str) -> List[Dict[str, str]]:
        """
        Calculates the Vimshottari Dasha timeline.
        dob format: 'YYYY-MM-DD'
        Returns list of sequential dicts: [{"planet": "Sun", "start": "2020-01-01", "end": "2026-01-01"}, ...]
        """
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
            current_date = datetime.utcnow() # fallback
            
        timeline = []
        
        # Push the balance dasha first
        end_date = current_date + timedelta(days=balance_years * 365.2425)
        timeline.append({
            "planet": start_planet,
            "start": current_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d")
        })
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
            current_date = end_date
            current_idx = (current_idx + 1) % 9
            
        return timeline
