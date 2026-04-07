import re
from pathlib import Path

from PyQt6.QtWidgets import QFileDialog, QMessageBox
from app.ui.main_window import MainWindow
from app.services.horoscope_service import HoroscopeService
from app.services.horoscope_chat_service import HoroscopeChatService
from app.services.app_settings_service import AppSettingsService
from app.services.openai_refiner_service import OpenAIRefinerService
from app.services.report_service import ReportService
from app.repositories.database_manager import DatabaseManager

class MainController:
    """Acts as the bridge between UI inputs and Backend logic/storage."""
    def __init__(self, db_manager: DatabaseManager):
        self.service = HoroscopeService(db_manager)
        self.report_service = ReportService(db_manager)
        self.settings_service = AppSettingsService()
        self.ai_refiner_service = OpenAIRefinerService(self.settings_service)
        self.chat_service = HoroscopeChatService(
            horoscope_service=self.service,
            ai_refiner=self.ai_refiner_service,
        )
        self.active_user_id = None
        
        # Instantiate UI
        self.view = MainWindow()
        self.view.chat_screen.configure_chat_service(self.chat_service)
        initial_settings = self.settings_service.load()
        self.view.settings_screen.load_settings(initial_settings)
        self.view.chat_screen.set_mode_badge("openai" if initial_settings.get("ai_enabled") else "local")
        
        # Connect signals
        self.view.input_form.generate_requested.connect(self.handle_generate)
        self.view.input_form.save_requested.connect(self.handle_save)
        
        self.view.user_list_screen.load_requested.connect(self.handle_load_user)
        self.view.user_list_screen.delete_requested.connect(self.handle_delete_user)
        
        self.view.rule_editor_screen.save_rule_requested.connect(self.handle_save_rule)
        self.view.chart_display.generate_report_requested.connect(self.handle_generate_report)
        self.view.timeline_view.period_selected.connect(self.handle_timeline_period_selected)
        self.view.settings_screen.save_requested.connect(self.handle_save_settings)
        
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
            self._populate_advanced_views(user_id)

            # Switch back to Chart Generator tab
            self.view.tabs.setCurrentIndex(0)
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self.view, "Error", f"Failed to load chart: {str(e)}")

    def handle_delete_user(self, user_id: int):
        try:
            self.service.delete_user(user_id)
            if self.active_user_id == user_id:
                self.active_user_id = None
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
                self._populate_advanced_views(latest_user.id)
            
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

    def handle_generate_report(self):
        """Prompts for a file path and generates the current user's PDF report."""
        if self.active_user_id is None:
            QMessageBox.warning(self.view, "No User", "Please generate or load a chart first.")
            return

        user_model = self.service.user_repo.get_by_id(self.active_user_id)
        default_filename = self._build_report_filename(user_model.name if user_model else "")
        default_path = str((Path.cwd() / default_filename).resolve())
        output_path, _ = QFileDialog.getSaveFileName(
            self.view,
            "Save Horoscope Report",
            default_path,
            "PDF Files (*.pdf)",
        )
        if not output_path:
            return

        try:
            saved_path = self.report_service.generate_pdf(self.active_user_id, output_path)
            QMessageBox.information(
                self.view,
                "Report Generated",
                f"Horoscope report saved successfully.\n{saved_path}",
            )
        except Exception as exc:
            QMessageBox.critical(self.view, "Report Error", f"Failed to generate report: {exc}")

    def handle_timeline_period_selected(self, period_data: dict):
        """Shows detailed predictions for a clicked dasha period."""
        planet = period_data.get("planet", "Unknown")
        start = period_data.get("start", "")
        end = period_data.get("end", "")
        events = period_data.get("events", [])

        lines = [f"{planet} Dasha", f"{start} to {end}", ""]
        if events:
            lines.append("Predictions:")
            for event in events:
                event_type = str(event.get("type", "general")).title()
                confidence = str(event.get("confidence", "medium")).title()
                summary = str(event.get("summary", "")).strip() or "No detailed summary available."
                lines.append(f"- {event_type} ({confidence}): {summary}")
        else:
            lines.append("No detailed predictions available for this period.")

        QMessageBox.information(
            self.view,
            f"{planet} Timeline Details",
            "\n".join(lines),
        )

    def handle_save_settings(self, settings_data: dict):
        """Persists app settings and keeps chat mode available with graceful fallback."""
        try:
            saved_settings = self.settings_service.save(settings_data)
            self.view.settings_screen.load_settings(saved_settings)

            mode_text = "OpenAI enhancement enabled" if saved_settings.get("ai_enabled") else "Local chat only"
            QMessageBox.information(
                self.view,
                "Settings Saved",
                f"Settings saved successfully.\nMode: {mode_text}",
            )
            self.view.chat_screen.set_mode_badge("openai" if saved_settings.get("ai_enabled") else "local")
            self.view.chat_screen.append_system_message(
                f"Chat settings updated. Current mode: {mode_text}."
            )
        except Exception as exc:
            QMessageBox.critical(self.view, "Settings Error", f"Failed to save settings: {exc}")

    def _build_report_filename(self, user_name: str) -> str:
        """Builds a filesystem-safe default report filename from the active user name."""
        cleaned_name = re.sub(r"[^A-Za-z0-9]+", "_", str(user_name or "").strip()).strip("_")
        if not cleaned_name:
            cleaned_name = "Horoscope"
        return f"{cleaned_name}_Horoscope_Report.pdf"

    def _populate_advanced_views(self, user_id: int):
        """Refreshes advanced analysis tabs, including the life timeline."""
        from app.services.astrology_advanced_service import AstrologyAdvancedService
        import json

        advanced_service = AstrologyAdvancedService()
        user_model = self.service.user_repo.get_by_id(user_id)
        if not user_model:
            self.view.timeline_view.clear_timeline()
            return

        chart_models = self.service.chart_repo.get_by_user_id(user_id)
        advanced_data = advanced_service.generate_advanced_data(chart_models, user_model.dob)
        self.view.aspects_view.setText(json.dumps(advanced_data["aspects"], indent=2))
        self.view.dasha_view.setText(json.dumps(advanced_data["dasha"], indent=2))
        self.view.navamsha_view.setText(json.dumps(advanced_data["navamsha"], indent=2))
        self.view.plugins_view.setText(json.dumps(advanced_data["plugins"], indent=2))
        self.active_user_id = user_id
        self.view.chat_screen.set_active_user(user_id)

        timeline_data = self.service.get_timeline_data(user_id)
        self.view.timeline_view.set_timeline_data(timeline_data)

    def show(self):
        self.view.show()
