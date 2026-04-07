from typing import Dict, List, Any

class AspectsEngine:
    """Calculates planetary aspects based on Vedic Astrology rules."""
    
    def __init__(self):
        # Default 7th house aspect for all planets
        self.default_aspect = [7]
        
        # Special aspects based on planetary nature
        self.special_aspects = {
            "Mars": [4, 7, 8],
            "Jupiter": [5, 7, 9],
            "Saturn": [3, 7, 10],
            # Including Rahu and Ketu's traditional Jupiter-like aspects
            "Rahu": [5, 7, 9],
            "Ketu": [5, 7, 9]
        }
        
        # Planets capable of casting aspects
        self.valid_planets = {"Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"}

    def get_aspects(self, planet_name: str) -> List[int]:
        """Returns the relative house integers a planet aspects."""
        if planet_name in self.special_aspects:
            return self.special_aspects[planet_name]
        return self.default_aspect

    def calculate_aspects(self, chart_data: Dict[str, Dict[str, int]]) -> Dict[str, List[Dict[str, int]]]:
        """
        Input: {"Saturn": {"house": 10}, "Moon": {"house": 4}}
        Output: {"Saturn": [{"aspect_house": 12}, {"aspect_house": 4}, {"aspect_house": 7}]}
        """
        results = {}
        for planet, data in chart_data.items():
            if planet not in self.valid_planets:
                continue
                
            current_house = data.get("house")
            if not current_house:
                continue
                
            aspects_list = self.get_aspects(planet)
            planet_aspects = []
            
            for aspect_offset in aspects_list:
                # Calculate circular house placement (1 to 12)
                # Example: House 10 + Aspect 3 = 10 + 3 - 1 = 12. 
                # House 10 + Aspect 4 = 10 + 4 - 1 = 13 -> 1.
                target_house = (current_house + aspect_offset - 2) % 12 + 1
                planet_aspects.append({"aspect_house": target_house})
                
            results[planet] = planet_aspects
            
        return results
