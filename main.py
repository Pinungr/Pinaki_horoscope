import sys
from PyQt6.QtWidgets import QApplication
from app.config.config_loader import get_astrology_config
from app.utils.logger import setup_logging, get_logger

logger = get_logger(__name__)

def main():
    setup_logging()
    logger.info("Initializing Horoscope Application UI...")
    logger.info("Active astrology config: %s", get_astrology_config())
    
    # Initialize DB Schema
    from app.repositories.database_manager import DatabaseManager
    db_manager = DatabaseManager()
    db_manager.initialize_schema()
    
    app = QApplication(sys.argv)
    
    from app.controllers.main_controller import MainController
    controller = MainController(db_manager)
    controller.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
