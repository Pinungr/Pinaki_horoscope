import sys
import logging
from PyQt6.QtWidgets import QApplication
from app.ui.main_window import MainWindow

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def main():
    logger.info("Initializing Horoscope Application UI...")
    
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
