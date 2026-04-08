import re
from pathlib import Path
import logging

from PyQt6.QtWidgets import QFileDialog, QMessageBox
from app.ui.main_window import MainWindow
from app.services.horoscope_service import HoroscopeService
from app.services.horoscope_chat_service import HoroscopeChatService
from app.services.app_settings_service import AppSettingsService
from app.services.language_manager import LanguageManager
from app.services.openai_refiner_service import OpenAIRefinerService
from app.services.report_service import ReportService
from app.repositories.database_manager import DatabaseManager
from app.utils.safe_execution import AppError
from app.utils.logger import log_user_action


logger = logging.getLogger(__name__)

class MainController:
    """Acts as the bridge between UI inputs and Backend logic/storage."""
    def __init__(self, db_manager: DatabaseManager):
        self.service = HoroscopeService(db_manager)
        self.report_service = ReportService(db_manager)
        self.settings_service = AppSettingsService()
        initial_settings = self.settings_service.load()
        self.language_manager = LanguageManager(str(initial_settings.get("language_code", "en")))
        self.ai_refiner_service = OpenAIRefinerService(self.settings_service)
        self.chat_service = HoroscopeChatService(
            horoscope_service=self.service,
            ai_refiner=self.ai_refiner_service,
        )
        self.active_user_id = None
        
        # Instantiate UI
        self.view = MainWindow(language_manager=self.language_manager)
        self.view.chat_screen.configure_chat_service(self.chat_service)
        self.view.settings_screen.load_settings(initial_settings)
        self.view.chat_screen.set_mode_badge("openai" if initial_settings.get("ai_enabled") else "local")
        
        # Connect signals
        self.view.input_form.generate_requested.connect(self.handle_generate)
        self.view.input_form.save_requested.connect(self.handle_save)
        self.view.input_form.state_changed.connect(self.handle_state_changed)
        self.view.input_form.city_changed.connect(self.handle_city_changed)
        
        self.view.user_list_screen.load_requested.connect(self.handle_load_user)
        self.view.user_list_screen.delete_requested.connect(self.handle_delete_user)
        
        self.view.rule_editor_screen.save_rule_requested.connect(self.handle_save_rule)
        self.view.chart_display.generate_report_requested.connect(self.handle_generate_report)
        self.view.timeline_view.period_selected.connect(self.handle_timeline_period_selected)
        self.view.settings_screen.language_changed.connect(self.handle_language_changed)
        self.view.settings_screen.save_requested.connect(self.handle_save_settings)
        
        # Populate initial user list
        self._load_location_options()
        self.refresh_user_list()

    @staticmethod
    def _friendly_error(exc: Exception, fallback_message: str) -> str:
        """Maps internal exceptions to safe UI text."""
        if isinstance(exc, AppError):
            return exc.user_message
        return fallback_message

    def handle_save_rule(self, rule_data: dict):
        try:
            log_user_action("controller_save_rule", category=rule_data.get("category", "general"))
            self.service.save_astrology_rule(rule_data)
            self.view.rule_editor_screen.clear_form()
            QMessageBox.information(self.view, "Success", "Rule saved successfully!")
        except Exception as e:
            logger.exception("Failed to save rule: %s", e)
            QMessageBox.critical(self.view, "Error", self._friendly_error(e, "Failed to save rule."))

    def refresh_user_list(self):
        try:
            users_data = self.service.get_all_users_dicts()
            self.view.user_list_screen.populate_users(users_data)
        except Exception as e:
            logger.exception("Failed to load users: %s", e)
            QMessageBox.critical(self.view, "Error", self._friendly_error(e, "Failed to load users."))

    def handle_load_user(self, user_id: int):
        try:
            log_user_action("controller_load_user", user_id=user_id)
            display_data, predictions = self.service.load_chart_for_user(user_id)
            user_model = self.service.user_repo.get_by_id(user_id)
            self.view.chart_display.display_chart(
                display_data,
                self._build_chart_header(user_model) if user_model else None,
            )
            self.view.chart_display.display_predictions(predictions)
            self._populate_advanced_views(user_id)

            # Switch back to Chart Generator tab
            self.view.tabs.setCurrentIndex(0)
        except Exception as e:
            logger.exception("Failed to load chart for user %s: %s", user_id, e)
            QMessageBox.critical(self.view, "Error", self._friendly_error(e, "Failed to load chart."))

    def handle_delete_user(self, user_id: int):
        try:
            log_user_action("controller_delete_user", user_id=user_id)
            self.service.delete_user(user_id)
            if self.active_user_id == user_id:
                self.active_user_id = None
            self.refresh_user_list()
        except Exception as e:
            logger.exception("Failed to delete user %s: %s", user_id, e)
            QMessageBox.critical(self.view, "Error", self._friendly_error(e, "Failed to delete user."))

    def handle_generate(self, user_data: dict):
        try:
            log_user_action("controller_generate", name=user_data.get("name"), state=user_data.get("state"), city=user_data.get("city"))
            validated_data = self.service.prepare_user_input(user_data)

            # 1. Generate and save phase 1 data
            display_data, predictions = self.service.generate_and_save_chart(validated_data)
            self.view.chart_display.display_chart(display_data, self._build_chart_header(validated_data))
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
            logger.exception("Failed to generate chart: %s", e)
            QMessageBox.critical(
                self.view,
                "Error",
                self._friendly_error(e, str(e) if isinstance(e, ValueError) else "Failed to generate chart."),
            )

    def handle_save(self, user_data: dict):
        try:
            log_user_action("controller_validate_input", name=user_data.get("name"))
            self.service.prepare_user_input(user_data)
            QMessageBox.information(
                self.view,
                "Info",
                "Input is valid. Save is handled automatically during Generate.",
            )
        except Exception as exc:
            logger.warning("Input validation failed: %s", exc)
            QMessageBox.warning(self.view, "Validation Error", str(exc))

    def handle_state_changed(self, state: str):
        """Loads cities for the selected state into the input form."""
        try:
            log_user_action("controller_select_state", state=state)
            cities = self.service.get_cities_for_state(state)
            self.view.input_form.set_cities(cities)
        except Exception as exc:
            logger.exception("Failed to load cities for state %s: %s", state, exc)
            QMessageBox.warning(self.view, "Location Error", self._friendly_error(exc, "Failed to load cities."))

    def handle_city_changed(self, state: str, city: str):
        """Auto-fills coordinates from the selected city."""
        try:
            log_user_action("controller_select_city", state=state, city=city)
            location = self.service.get_location_details(state, city)
            self.view.input_form.set_location_details(
                state=location["state"],
                city=location["city"],
                latitude=location["latitude"],
                longitude=location["longitude"],
            )
        except Exception as exc:
            logger.exception("Failed to load location details for %s, %s: %s", city, state, exc)
            QMessageBox.warning(self.view, "Location Error", self._friendly_error(exc, "Failed to load location details."))

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
            log_user_action("controller_generate_report", user_id=self.active_user_id, output_path=output_path)
            saved_path = self.report_service.generate_pdf(self.active_user_id, output_path)
            QMessageBox.information(
                self.view,
                "Report Generated",
                f"Horoscope report saved successfully.\n{saved_path}",
            )
        except Exception as exc:
            logger.exception("Failed to generate report for user %s: %s", self.active_user_id, exc)
            QMessageBox.critical(self.view, "Report Error", self._friendly_error(exc, "Failed to generate report."))

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
            log_user_action("controller_save_settings", ai_enabled=settings_data.get("ai_enabled"))
            saved_settings = self.settings_service.save(settings_data)
            self.language_manager.set_language(str(saved_settings.get("language_code", "en")))
            self.view.apply_translations()
            self.view.settings_screen.load_settings(saved_settings)

            mode_text = self.language_manager.get_text("ui.mode_openai") if saved_settings.get("ai_enabled") else self.language_manager.get_text("ui.mode_local")
            QMessageBox.information(
                self.view,
                self.language_manager.get_text("ui.settings_saved_title"),
                self.language_manager.get_text("ui.settings_saved_message").format(mode=mode_text),
            )
            self.view.chat_screen.set_mode_badge("openai" if saved_settings.get("ai_enabled") else "local")
            self.view.chat_screen.append_system_message(
                f"Chat settings updated. Current mode: {mode_text}."
            )
        except Exception as exc:
            logger.exception("Failed to save settings: %s", exc)
            QMessageBox.critical(self.view, "Settings Error", self._friendly_error(exc, "Failed to save settings."))

    def handle_language_changed(self, language_code: str):
        """Applies a newly selected language immediately without restart."""
        self.language_manager.set_language(language_code)
        self.view.apply_translations()

    def _build_report_filename(self, user_name: str) -> str:
        """Builds a filesystem-safe default report filename from the active user name."""
        cleaned_name = re.sub(r"[^A-Za-z0-9]+", "_", str(user_name or "").strip()).strip("_")
        if not cleaned_name:
            cleaned_name = "Horoscope"
        return f"{cleaned_name}_Horoscope_Report.pdf"

    def _build_chart_header(self, source: object) -> dict:
        """Builds stable presentation metadata for the chart header."""
        if isinstance(source, dict):
            name = str(source.get("name", "")).strip()
            dob = str(source.get("dob", "")).strip()
            tob = str(source.get("tob", "")).strip()
            place = str(source.get("place", "")).strip()
        else:
            name = str(getattr(source, "name", "")).strip()
            dob = str(getattr(source, "dob", "")).strip()
            tob = str(getattr(source, "tob", "")).strip()
            place = str(getattr(source, "place", "")).strip()

        return {
            "title": "Birth Chart",
            "name": name,
            "dob": dob,
            "tob": tob,
            "place": place,
        }

    def _load_location_options(self):
        """Loads the state dropdown from the local location database."""
        try:
            states = self.service.get_available_states()
            self.view.input_form.set_states(states)
        except Exception as exc:
            logger.exception("Failed to load states: %s", exc)
            QMessageBox.warning(self.view, "Location Error", self._friendly_error(exc, "Failed to load states."))

    def _populate_advanced_views(self, user_id: int):
        """Refreshes advanced analysis tabs, including the life timeline."""
        from app.services.astrology_advanced_service import AstrologyAdvancedService
        import json

        try:
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
        except Exception as exc:
            logger.exception("Failed to populate advanced views for user %s: %s", user_id, exc)
            self.view.aspects_view.setText("{}")
            self.view.dasha_view.setText("[]")
            self.view.navamsha_view.setText("{}")
            self.view.plugins_view.setText("{}")
            self.view.timeline_view.clear_timeline()
            QMessageBox.warning(
                self.view,
                "Advanced Analysis",
                self._friendly_error(exc, "Some advanced analysis could not be loaded right now."),
            )

    def show(self):
        self.view.show()
