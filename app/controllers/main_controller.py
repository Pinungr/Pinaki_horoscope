import re
from pathlib import Path
import logging
import os
from contextlib import contextmanager

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox
from app.ui.main_window import MainWindow
from app.services.horoscope_service import HoroscopeService
from app.services.horoscope_chat_service import HoroscopeChatService
from app.services.app_settings_service import AppSettingsService
from app.services.language_manager import LanguageManager
from app.services.openai_refiner_service import OpenAIRefinerService
from app.services.report_service import ReportService
from app.repositories.database_manager import DatabaseManager
from app.utils.cache import get_astrology_cache
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
        self.chat_service.set_language(str(initial_settings.get("language_code", "en")))
        self.cache = get_astrology_cache()
        self.debug_ui_enabled = self._is_debug_ui_enabled()
        self.active_user_id = None
        
        # Instantiate UI
        self.view = MainWindow(language_manager=self.language_manager)
        self.view.chat_screen.configure_chat_service(self.chat_service)
        self.view.settings_screen.load_settings(initial_settings)
        self.view.chat_screen.set_mode_badge("openai" if initial_settings.get("ai_enabled") else "local")
        self.view.chart_display.set_cache_debug_mode(self.debug_ui_enabled)
        
        # Connect signals
        self.view.input_form.generate_requested.connect(self.handle_generate)
        self.view.input_form.save_requested.connect(self.handle_save)
        self.view.input_form.state_changed.connect(self.handle_state_changed)
        self.view.input_form.city_changed.connect(self.handle_city_changed)
        
        self.view.user_list_screen.load_requested.connect(self.handle_load_user)
        self.view.user_list_screen.delete_requested.connect(self.handle_delete_user)
        
        self.view.rule_editor_screen.save_rule_requested.connect(self.handle_save_rule)
        self.view.chart_display.generate_report_requested.connect(self.handle_generate_report)
        self.view.chart_display.area_filter_changed.connect(self.view.timeline_view.set_event_filter)
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
            with self._busy_feedback(users_mode="refresh"):
                users_data = self.service.get_all_users_dicts()
                self.view.user_list_screen.populate_users(users_data)
        except Exception as e:
            logger.exception("Failed to load users: %s", e)
            QMessageBox.critical(self.view, "Error", self._friendly_error(e, "Failed to load users."))

    def handle_load_user(self, user_id: int):
        try:
            with self._busy_feedback(users_mode="load", chart_status="Loading saved chart..."):
                log_user_action("controller_load_user", user_id=user_id)
                chart_cache_hit = self._is_chart_cache_hit(user_id)
                display_data, predictions = self.service.load_chart_for_user(user_id)
                user_model = self.service.user_repo.get_by_id(user_id)
                self.view.chart_display.display_chart(
                    display_data,
                    self._build_chart_header(user_model) if user_model else None,
                )
                self.view.chart_display.display_predictions(predictions)
                self._populate_advanced_views(user_id, chart_cache_hit=chart_cache_hit)

                # Switch back to Chart Generator tab
                self.view.tabs.setCurrentIndex(0)
            self.view.chart_display.set_status("Chart loaded successfully.", "success")
        except Exception as e:
            logger.exception("Failed to load chart for user %s: %s", user_id, e)
            self.view.chart_display.set_status("Failed to load chart. Please try again.", "error")
            QMessageBox.critical(self.view, "Error", self._friendly_error(e, "Failed to load chart."))

    def handle_delete_user(self, user_id: int):
        try:
            with self._busy_feedback(users_mode="delete", chart_status="Deleting selected profile..."):
                log_user_action("controller_delete_user", user_id=user_id)
                self.service.delete_user(user_id)
                if self.active_user_id == user_id:
                    self.active_user_id = None
                self.refresh_user_list()
            self.view.chart_display.set_status("Profile deleted successfully.", "success")
        except Exception as e:
            logger.exception("Failed to delete user %s: %s", user_id, e)
            self.view.chart_display.set_status("Profile deletion failed. Please retry.", "error")
            QMessageBox.critical(self.view, "Error", self._friendly_error(e, "Failed to delete user."))

    def handle_generate(self, user_data: dict):
        try:
            with self._busy_feedback(form_mode="generate", chart_status="Generating chart and predictions..."):
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
                    self._populate_advanced_views(latest_user.id, chart_cache_hit=False)
                
                # Automatically refresh user list to include the newly generated user
                self.refresh_user_list()
                # Switch back to Chart Generator tab if not already
                self.view.tabs.setCurrentIndex(0)
            self.view.input_form.set_status("Chart generated successfully.", "success")
            self.view.chart_display.set_status("Fresh predictions are now ready.", "success")
        except Exception as e:
            logger.exception("Failed to generate chart: %s", e)
            self.view.input_form.set_status("Chart generation failed. Please verify details and retry.", "error")
            self.view.chart_display.set_status("Chart generation failed. Please retry.", "error")
            QMessageBox.critical(
                self.view,
                "Error",
                self._friendly_error(e, str(e) if isinstance(e, ValueError) else "Failed to generate chart."),
            )

    def handle_save(self, user_data: dict):
        try:
            with self._busy_feedback(form_mode="save"):
                log_user_action("controller_validate_input", name=user_data.get("name"))
                self.service.prepare_user_input(user_data)
            QMessageBox.information(
                self.view,
                "Info",
                "Input is valid. Save is handled automatically during Generate.",
            )
            self.view.input_form.set_status("Input validated. Use Generate Chart to save and analyze.", "success")
        except Exception as exc:
            logger.warning("Input validation failed: %s", exc)
            self.view.input_form.set_status(str(exc), "error")
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
            with self._busy_feedback(report_busy=True, chart_status="Generating your PDF report..."):
                log_user_action("controller_generate_report", user_id=self.active_user_id, output_path=output_path)
                saved_path = self.report_service.generate_pdf(
                    self.active_user_id,
                    output_path,
                    language=self.language_manager.current_language,
                )
            QMessageBox.information(
                self.view,
                "Report Generated",
                f"Horoscope report saved successfully.\n{saved_path}",
            )
            self.view.chart_display.set_status("PDF report generated successfully.", "success")
        except Exception as exc:
            logger.exception("Failed to generate report for user %s: %s", self.active_user_id, exc)
            self.view.chart_display.set_status("PDF generation failed. Please try another path.", "error")
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
            self.chat_service.set_language(self.language_manager.current_language)
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
            self.view.chart_display.set_cache_debug_mode(self.debug_ui_enabled)
        except Exception as exc:
            logger.exception("Failed to save settings: %s", exc)
            QMessageBox.critical(self.view, "Settings Error", self._friendly_error(exc, "Failed to save settings."))

    def handle_language_changed(self, language_code: str):
        """Applies a newly selected language immediately without restart."""
        self.language_manager.set_language(language_code)
        self.chat_service.set_language(self.language_manager.current_language)
        self.view.apply_translations()
        self.cache.clear(
            namespaces=(
                "advanced_data",
                "timeline",
                "ui_advanced_data",
                "ui_timeline_forecast",
                "chat_advanced_data",
                "chat_timeline_forecast",
            )
        )
        if self.active_user_id is not None:
            self._populate_advanced_views(self.active_user_id)

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

    def _populate_advanced_views(self, user_id: int, chart_cache_hit: bool | None = None):
        """Refreshes advanced analysis tabs, including the life timeline."""
        from app.services.astrology_advanced_service import AstrologyAdvancedService
        from app.services.timeline_service import TimelineService
        import json

        try:
            user_model = self.service.user_repo.get_by_id(user_id)
            if not user_model:
                self.view.timeline_view.clear_timeline()
                return

            active_language = self.language_manager.current_language
            advanced_data = self.cache.get("ui_advanced_data", user_id)
            advanced_cache_hit = False
            if isinstance(advanced_data, dict):
                cached_language = str(advanced_data.get("_language", "en")).strip().lower() or "en"
                advanced_cache_hit = cached_language == active_language
                if not advanced_cache_hit:
                    advanced_data = None
            elif advanced_data is not None and active_language == "en":
                advanced_cache_hit = True
            if advanced_data is None:
                chart_models = self.service.chart_repo.get_by_user_id(user_id)
                advanced_service = AstrologyAdvancedService()
                advanced_data = advanced_service.generate_advanced_data(
                    chart_models,
                    user_model.dob,
                    language=active_language,
                )
                self.cache.set("ui_advanced_data", user_id, advanced_data)

            self.view.aspects_view.setText(json.dumps(advanced_data["aspects"], indent=2))
            self.view.dasha_view.setText(json.dumps(advanced_data["dasha"], indent=2))
            self.view.navamsha_view.set_navamsha_data(advanced_data["navamsha"])
            self.view.plugins_view.setText(json.dumps(advanced_data["plugins"], indent=2))
            unified_summary = {}
            unified_payload = advanced_data.get("unified", {}) if isinstance(advanced_data, dict) else {}
            if isinstance(unified_payload, dict):
                unified_summary = dict(unified_payload.get("summary", {}) or {})
                top_areas = unified_summary.get("top_areas", [])
                if isinstance(top_areas, list):
                    unified_summary["top_areas"] = [
                        "finance" if str(area).strip().lower() in {"wealth", "financial"} else str(area).strip().lower()
                        for area in top_areas
                        if str(area or "").strip()
                    ]
            self.view.chart_display.display_top_insights(unified_summary)
            self.active_user_id = user_id
            self.view.chat_screen.set_active_user(user_id)

            timeline_data = self.service.get_timeline_data(user_id, language=self.language_manager.current_language)
            unified_predictions = []
            if isinstance(unified_payload, dict):
                raw_predictions = unified_payload.get("predictions", [])
                if isinstance(raw_predictions, list):
                    unified_predictions = [dict(item) for item in raw_predictions if isinstance(item, dict)]

            timeline_forecast = self.cache.get("ui_timeline_forecast", user_id)
            timeline_cache_hit = False
            if isinstance(timeline_forecast, dict):
                cached_language = str(timeline_forecast.get("_language", "en")).strip().lower() or "en"
                timeline_cache_hit = cached_language == active_language
                if not timeline_cache_hit:
                    timeline_forecast = None
            elif timeline_forecast is not None and active_language == "en":
                timeline_cache_hit = True
            if timeline_forecast is None:
                timeline_forecast = TimelineService().build_timeline_forecast(
                    unified_predictions,
                    advanced_data.get("dasha", []) if isinstance(advanced_data, dict) else [],
                    language=active_language,
                )
                if isinstance(timeline_forecast, dict):
                    timeline_forecast["_language"] = active_language
                self.cache.set("ui_timeline_forecast", user_id, timeline_forecast)

            forecast_rows = timeline_forecast.get("timeline", []) if isinstance(timeline_forecast, dict) else []
            if isinstance(forecast_rows, list) and forecast_rows:
                self.view.timeline_view.set_timeline_data({"mode": "forecast", "timeline": forecast_rows})
            else:
                self.view.timeline_view.set_timeline_data(timeline_data)

            self._update_cache_debug_badge(
                chart_hit=chart_cache_hit,
                advanced_hit=advanced_cache_hit,
                timeline_hit=timeline_cache_hit,
            )
        except Exception as exc:
            logger.exception("Failed to populate advanced views for user %s: %s", user_id, exc)
            self.view.aspects_view.setText("{}")
            self.view.dasha_view.setText("[]")
            self.view.navamsha_view.clear()
            self.view.plugins_view.setText("{}")
            self.view.timeline_view.clear_timeline()
            self._update_cache_debug_badge(
                chart_hit=chart_cache_hit,
                advanced_hit=None,
                timeline_hit=None,
            )
            QMessageBox.warning(
                self.view,
                "Advanced Analysis",
                self._friendly_error(exc, "Some advanced analysis could not be loaded right now."),
            )

    def show(self):
        self.view.show()

    def _is_chart_cache_hit(self, user_id: int) -> bool:
        """Checks whether the chart-display and prediction caches are both available."""
        return (
            self.cache.get("chart_display", user_id) is not None
            and self.cache.get("predictions", user_id) is not None
        )

    def _update_cache_debug_badge(
        self,
        *,
        chart_hit: bool | None = None,
        advanced_hit: bool | None = None,
        timeline_hit: bool | None = None,
    ) -> None:
        """Updates the debug-only cache badge with compact HIT/MISS segments."""
        if not self.debug_ui_enabled:
            return

        segments = []
        flags: list[bool] = []
        for label, flag in (
            ("Chart", chart_hit),
            ("Advanced", advanced_hit),
            ("Timeline", timeline_hit),
        ):
            if flag is None:
                continue
            segments.append(f"{label} {'HIT' if flag else 'MISS'}")
            flags.append(flag)

        if not segments:
            self.view.chart_display.set_cache_debug_status("", None)
            return

        if flags and all(flags):
            aggregate = True
        elif flags and not any(flags):
            aggregate = False
        else:
            aggregate = None

        self.view.chart_display.set_cache_debug_status(" | ".join(segments), aggregate)

    def _is_debug_ui_enabled(self) -> bool:
        """Enables debug widgets when explicit env flag is set."""
        value = str(os.getenv("HOROSCOPE_DEBUG_UI", "")).strip().lower()
        return value in {"1", "true", "yes", "on"}

    @contextmanager
    def _busy_feedback(
        self,
        *,
        form_mode: str | None = None,
        users_mode: str | None = None,
        chart_status: str | None = None,
        report_busy: bool = False,
    ):
        """Applies coordinated busy states so long operations feel responsive."""
        try:
            if form_mode:
                self.view.input_form.set_busy(True, form_mode)
            if users_mode:
                self.view.user_list_screen.set_busy(True, users_mode)
            if report_busy:
                self.view.chart_display.set_report_busy(True)
            if chart_status:
                self.view.chart_display.set_status(chart_status, "info")
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            QApplication.processEvents()
            yield
        finally:
            if report_busy:
                self.view.chart_display.set_report_busy(False)
            if form_mode:
                self.view.input_form.set_busy(False, form_mode)
            if users_mode:
                self.view.user_list_screen.set_busy(False, users_mode)
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()
            QApplication.processEvents()
