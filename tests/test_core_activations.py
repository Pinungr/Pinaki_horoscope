import unittest
import logging
import traceback
from app.services.horoscope_service import HoroscopeService
from app.services.astrology_advanced_service import AstrologyAdvancedService
from app.repositories.database_manager import DatabaseManager
from app.models.domain import User

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class TestCoreActivations(unittest.TestCase):
    def setUp(self):
        self.db_manager = DatabaseManager("test_core.db")
        self.db_manager.initialize_schema()
        self.horoscope_service = HoroscopeService(self.db_manager)
        self.advanced_service = AstrologyAdvancedService()

    def test_shadbala_integration(self):
        # Create a user data dict
        user_data = {"name": "Test User", "dob": "1990-01-01", "tob": "12:00", "place": "New Delhi", "latitude": 28.6, "longitude": 77.2}
        
        # This will trigger chart generation and shadbala calculation
        display_data, predictions = self.horoscope_service.generate_and_save_chart(user_data)
        
        # Get user ID (most recent save)
        with self.db_manager.connection_context() as conn:
            user_id = conn.execute("SELECT id FROM users ORDER BY id DESC LIMIT 1").fetchone()[0]
        
        chart_data_models = self.horoscope_service.chart_repo.get_by_user_id(user_id)
        print(f"DEBUG: Saved Chart Rows: {[cd.planet_name for cd in chart_data_models]}")
        
        # Check if shadbala was cached
        shadbala = self.horoscope_service.cache.get("shadbala", user_id)
        print(f"Shadbala keys: {shadbala.keys() if shadbala else 'None'}")
        self.assertIsNotNone(shadbala)
        self.assertIn("sun", shadbala)
        self.assertIn("total", shadbala["sun"])
        for key in (
            "planet",
            "sthana_bala",
            "dik_bala",
            "kala_bala",
            "chestha_bala",
            "naisargika_bala",
            "drik_bala",
            "is_vargottama",
            "total",
        ):
            self.assertIn(key, shadbala["sun"])

    def test_transit_integration(self):
        # Create a user data dict
        user_data = {"name": "Transit Test", "dob": "1985-05-20", "tob": "08:00", "place": "Mumbai", "latitude": 19.07, "longitude": 72.87}
        self.horoscope_service.generate_and_save_chart(user_data)
        
        with self.db_manager.connection_context() as conn:
            user_id = conn.execute("SELECT id FROM users ORDER BY id DESC LIMIT 1").fetchone()[0]
        
        chart_data_models = self.horoscope_service.chart_repo.get_by_user_id(user_id)
        
        # Execute advanced analysis
        advanced_data = self.advanced_service.generate_advanced_data(chart_data_models, user_data["dob"])
        
        self.assertIn("transits", advanced_data)
        self.assertIn("sun", advanced_data["transits"]["transits"])
        print(f"Transit Sun House: {advanced_data['transits']['transits']['sun']['house_from_reference']}")

if __name__ == "__main__":
    import traceback
    try:
        unittest.main()
    except Exception:
        traceback.print_exc()
