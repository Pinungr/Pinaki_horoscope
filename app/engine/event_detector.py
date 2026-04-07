from typing import List, Dict
from app.models.domain import ChartData

class EventDetectorEngine:
    """Predicts specific life events based on planetary Dasha periods and their house placement."""

    def __init__(self):
        # House mappings for events
        self.event_houses = {
            10: "Career Phase",
            7: "Marriage / Partnership Period",
            2: "Financial Focus (Wealth/Savings)",
            11: "Financial Focus (Gains/Income)"
        }

    def detect_events(self, dasha_timeline: List[Dict[str, str]], chart_data: List[ChartData]) -> List[Dict[str, str]]:
        """
        Cross-references the Dasha timeline against planetary house placements
        to inject Event Predictor tags into the Dasha periods.
        """
        # Build quick lookup of Planet -> House
        planet_houses = {}
        for cd in chart_data:
            planet_houses[cd.planet_name] = cd.house
            
        enhanced_timeline = []
        for dasha in dasha_timeline:
            planet = dasha["planet"]
            # Copy original dasha dict
            enhanced_dasha = dict(dasha)
            
            # Default empty event
            events = []
            
            # Check placement
            if planet in planet_houses:
                house_placement = planet_houses[planet]
                if house_placement in self.event_houses:
                    events.append(self.event_houses[house_placement])
                    
            # Set the "events" key as a single string joined by commas
            enhanced_dasha["events"] = ", ".join(events) if events else "General Phase"
            enhanced_timeline.append(enhanced_dasha)
            
        return enhanced_timeline
