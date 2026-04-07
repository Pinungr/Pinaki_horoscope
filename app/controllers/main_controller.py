from PyQt6.QtWidgets import QMessageBox
from app.ui.main_window import MainWindow
from app.services.horoscope_service import HoroscopeService
from app.repositories.database_manager import DatabaseManager

class MainController:
    """Acts as the bridge between UI inputs and Backend logic/storage."""
    def __init__(self, db_manager: DatabaseManager):
        self.service = HoroscopeService(db_manager)
        
        # Instantiate UI
        self.view = MainWindow()
        
        # Connect signals
        self.view.input_form.generate_requested.connect(self.handle_generate)
        self.view.input_form.save_requested.connect(self.handle_save)
        
        self.view.user_list_screen.load_requested.connect(self.handle_load_user)
        self.view.user_list_screen.delete_requested.connect(self.handle_delete_user)
        
        self.view.rule_editor_screen.save_rule_requested.connect(self.handle_save_rule)
        
        # Populate initial user list
        self.refresh_user_list()

    def handle_save_rule(self, rule_data: dict):
        try:
            self.service.save_astrology_rule(rule_data)
            self.view.rule_editor_screen.clear_form()
            QMessageBox.information(self.view, "Success", "Rule saved successfully!")
        except Exception as e:
            QMessageBox.critical(self.view, "Error", f"Failed to save rule: {str(e)}")

    def refresh_user_list(self):
        try:
            users_data = self.service.get_all_users_dicts()
            self.view.user_list_screen.populate_users(users_data)
        except Exception as e:
            QMessageBox.critical(self.view, "Error", f"Failed to load users: {str(e)}")

    def handle_load_user(self, user_id: int):
        try:
            display_data, predictions = self.service.load_chart_for_user(user_id)
            self.view.chart_display.display_chart(display_data)
            self.view.chart_display.display_predictions(predictions)
            
            # Repopulate Advanced UI Tabs
            from app.services.astrology_advanced_service import AstrologyAdvancedService
            advanced_service = AstrologyAdvancedService()
            user_model = self.service.user_repo.get_by_id(user_id)
            if user_model:
                chart_models = self.service.chart_repo.get_by_user_id(user_id)
                advanced_data = advanced_service.generate_advanced_data(chart_models, user_model.dob)
                import json
                self.view.aspects_view.setText(json.dumps(advanced_data["aspects"], indent=2))
                self.view.dasha_view.setText(json.dumps(advanced_data["dasha"], indent=2))
                self.view.navamsha_view.setText(json.dumps(advanced_data["navamsha"], indent=2))
                self.view.plugins_view.setText(json.dumps(advanced_data["plugins"], indent=2))

            # Switch back to Chart Generator tab
            self.view.tabs.setCurrentIndex(0)
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self.view, "Error", f"Failed to load chart: {str(e)}")

    def handle_delete_user(self, user_id: int):
        try:
            self.service.delete_user(user_id)
            self.refresh_user_list()
        except Exception as e:
            QMessageBox.critical(self.view, "Error", f"Failed to delete user: {str(e)}")

    def handle_generate(self, user_data: dict):
        try:
            # 1. Generate and save phase 1 data
            display_data, predictions = self.service.generate_and_save_chart(user_data)
            self.view.chart_display.display_chart(display_data)
            self.view.chart_display.display_predictions(predictions)
            
            # 2. Fetch the newly saved DB models for advanced logic
            users = self.service.user_repo.get_all()
            if users:
                latest_user = users[-1]
                chart_models = self.service.chart_repo.get_by_user_id(latest_user.id)
                # 3. Process Phase 2 Advanced Logic
                from app.services.astrology_advanced_service import AstrologyAdvancedService
                advanced_service = AstrologyAdvancedService()
                advanced_data = advanced_service.generate_advanced_data(chart_models, latest_user.dob)
                
                # 4. Display
                import json
                self.view.aspects_view.setText(json.dumps(advanced_data["aspects"], indent=2))
                self.view.dasha_view.setText(json.dumps(advanced_data["dasha"], indent=2))
                self.view.navamsha_view.setText(json.dumps(advanced_data["navamsha"], indent=2))
                self.view.plugins_view.setText(json.dumps(advanced_data["plugins"], indent=2))
            
            # Automatically refresh user list to include the newly generated user
            self.refresh_user_list()
            # Switch back to Chart Generator tab if not already
            self.view.tabs.setCurrentIndex(0)
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self.view, "Error", str(e))

    def handle_save(self, user_data: dict):
        QMessageBox.information(self.view, "Info", "Save feature is implicitly handled during Generate!")

    def show(self):
        self.view.show()
