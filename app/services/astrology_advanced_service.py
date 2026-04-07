from typing import List, Dict
from app.models.domain import ChartData
from app.engine.aspects import AspectsEngine
from app.engine.dasha import DashaEngine
from app.engine.navamsha import NavamshaEngine

class AstrologyAdvancedService:
    """Service layer coordinating advanced astrological math engines."""

    def __init__(self):
        self.aspects_engine = AspectsEngine()
        self.dasha_engine = DashaEngine()
        self.navamsha_engine = NavamshaEngine()

    def generate_advanced_data(self, chart_data_models: List[ChartData], user_dob: str) -> Dict:
        """
        Coordinates the Aspects, Dasha, and Navamsha engines.
        Returns a master dictionary containing all three advanced analysis sets.
        """
        # 1. Transpile domain models to the dictionary shapes expected by engines
        # Aspects input: {"Planet": {"house": X}}
        aspects_input = {cd.planet_name: {"house": cd.house} for cd in chart_data_models}
        
        # Navamsha input: {"Planet": {"sign": "Aries", "degree": 15.5}}
        navamsha_input = {cd.planet_name: {"sign": cd.sign, "degree": cd.degree} for cd in chart_data_models}
        
        # Dasha input: Moon's absolute degree
        # Absolute degree is (SignIndex - 1) * 30 + local_degree
        signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
                 "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
        
        moon_absolute_longitude = 0.0
        for cd in chart_data_models:
            if cd.planet_name == "Moon":
                try:
                    sign_idx = signs.index(cd.sign)
                except ValueError:
                    sign_idx = 0
                moon_absolute_longitude = (sign_idx * 30.0) + cd.degree
                break

        # 2. Execute engines
        aspects_output = self.aspects_engine.calculate_aspects(aspects_input)
        navamsha_output = self.navamsha_engine.calculate_navamsha(navamsha_input)
        dasha_output = self.dasha_engine.calculate_dasha(moon_absolute_longitude, user_dob)

        # Step 17: Enhance Dasha with Event Detection Tags
        from app.engine.event_detector import EventDetectorEngine
        event_detector = EventDetectorEngine()
        dasha_output = event_detector.detect_events(dasha_output, chart_data_models)

        # Step 18: Execute all dynamic user-plugins seamlessly
        from app.plugins.plugin_manager import PluginManager
        from app.models.domain import User
        # Reconstruct a generic user stub for dob requirement (since we only have chart models explicitly passed here)
        user_stub = User(id=chart_data_models[0].user_id if chart_data_models else 0, dob=user_dob, name="", tob="", place="", latitude=0.0, longitude=0.0)
        plugin_manger = PluginManager()
        plugins_output = plugin_manger.execute_all(chart_data_models, user_stub)

        # 3. Compile Master Output
        return {
            "aspects": aspects_output,
            "navamsha": navamsha_output,
            "dasha": dasha_output,
            "plugins": plugins_output
        }
