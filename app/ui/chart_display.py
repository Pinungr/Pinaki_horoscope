from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from typing import List, Dict, Any, Optional
import re
from app.services.language_manager import LanguageManager
from core.predictions.prediction_service import get_prediction

class ChartDisplay(QWidget):
    generate_report_requested = pyqtSignal()

    def __init__(self, language_manager: LanguageManager | None = None):
        super().__init__()
        self.language_manager = language_manager or LanguageManager()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        self.title_label = QLabel()
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        from app.ui.widgets import ChartHeaderData, NorthIndianChartWidget

        self._chart_header_type = ChartHeaderData
        self.kundli_widget = NorthIndianChartWidget(language_manager=self.language_manager)
        self.kundli_widget.planet_hovered.connect(self._handle_planet_hovered)
        self.kundli_widget.house_hovered.connect(self._handle_house_hovered)
        self.kundli_widget.planet_clicked.connect(self._handle_planet_hovered)
        self.kundli_widget.house_clicked.connect(self._handle_house_clicked)
        self.kundli_widget.hover_cleared.connect(self._clear_chart_insight)
        self._latest_chart_data: List[Dict[str, Any]] = []
        self._current_header_payload: Optional[Dict[str, str]] = None
        self._prediction_display_state = "awaiting"
        
        self.predictions_label = QLabel()
        self.predictions_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 10px;")

        self.chart_insight_label = QLabel()
        self.chart_insight_label.setWordWrap(True)
        self.chart_insight_label.setStyleSheet(
            "background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; "
            "padding: 8px 10px; color: #334155; font-size: 12px;"
        )
        
        self.predictions_text = QLabel()
        self.predictions_text.setWordWrap(True)

        self.report_button = QPushButton()
        self.report_button.setEnabled(False)
        self.report_button.clicked.connect(self.generate_report_requested.emit)

        layout.addWidget(self.title_label)
        layout.addWidget(self.kundli_widget)
        layout.addWidget(self.chart_insight_label)
        layout.addWidget(self.predictions_label)
        layout.addWidget(self.predictions_text)
        layout.addWidget(self.report_button)
        
        self.setLayout(layout)
        self.apply_translations()

    def _tr(self, key: str) -> str:
        return self.language_manager.get_text(key)

    def apply_translations(self) -> None:
        self.title_label.setText(self._tr("ui.chart_information"))
        self.predictions_label.setText(f"{self._tr('ui.predictions')}:")
        self._clear_chart_insight()
        if self._prediction_display_state == "awaiting":
            self.predictions_text.setText(self._tr("ui.awaiting_generation"))
        elif self._prediction_display_state == "empty":
            self.predictions_text.setText(self._tr("ui.no_predictions_found"))
        self.report_button.setText(self._tr("ui.generate_report"))
        if self._current_header_payload is not None:
            self.kundli_widget.set_header_data(
                self._chart_header_type(
                    title=self._tr("ui.birth_chart"),
                    name=str(self._current_header_payload.get("name", "")),
                    dob=str(self._current_header_payload.get("dob", "")),
                    tob=str(self._current_header_payload.get("tob", "")),
                    place=str(self._current_header_payload.get("place", "")),
                )
            )
        self.kundli_widget.update()

    def display_chart(self, chart_data: List[Dict], header_data: Optional[Dict[str, str]] = None):
        """Renders chart rows and optional chart-header metadata."""
        self._latest_chart_data = list(chart_data)
        self._current_header_payload = dict(header_data) if header_data else None
        self.kundli_widget.set_chart_data(chart_data)

        if header_data:
            self.kundli_widget.set_header_data(
                self._chart_header_type(
                    title=self._tr("ui.birth_chart"),
                    name=str(header_data.get("name", "")),
                    dob=str(header_data.get("dob", "")),
                    tob=str(header_data.get("tob", "")),
                    place=str(header_data.get("place", "")),
                )
            )
        else:
            self.kundli_widget.clear_header_data()

        self._clear_chart_insight()
        self.report_button.setEnabled(bool(chart_data))

    def display_predictions(self, predictions: Any):
        """Show structured scored predictions without breaking older list-based payloads."""
        if not predictions:
            self.kundli_widget.clear_insights()
            self._prediction_display_state = "empty"
            self.predictions_text.setText(self._tr("ui.no_predictions_found"))
            return

        localized_predictions = self._localize_predictions(predictions)
        html = "<ul>"
        if isinstance(localized_predictions, dict):
            for category, details in localized_predictions.items():
                score = float(details.get("score", 0))
                confidence = str(details.get("confidence", "low")).upper()
                effect = str(details.get("effect", "neutral")).upper()
                summary = details.get("summary", "")
                if score < 0:
                    score_color = "#d9534f"
                elif score >= 2:
                    score_color = "#2d8f5b"
                elif score >= 1:
                    score_color = "#5bc0de"
                else:
                    score_color = "#777"
                html += f"<li style='margin-bottom: 8px;'>"
                html += f"<span style='color: white; background-color: {score_color}; border-radius: 3px; padding: 2px 4px; font-size: 10px; margin-right: 5px;'>"
                html += f"{category.upper()} | {score:.2f} | {confidence} | {effect}</span> "
                html += f"{summary}</li>"
        else:
            for p in localized_predictions:
                score_color = "#d9534f" if p["score"] > 50 else "#5bc0de" if p["score"] > 20 else "#777"
                html += f"<li style='margin-bottom: 5px;'>"
                html += f"<span style='color: white; background-color: {score_color}; border-radius: 3px; padding: 2px 4px; font-size: 10px; margin-right: 5px;'>"
                html += f"{p['category'].upper()} | {p['score']}</span> "
                html += f"{p['text']}</li>"
        html += "</ul>"

        self._prediction_display_state = "content"
        self.kundli_widget.set_insights(**self._build_chart_insights(localized_predictions))
        self.predictions_text.setText(html)

    def _handle_planet_hovered(self, payload: Dict[str, Any]) -> None:
        planet = self._translate_planet_name(str(payload.get("planet", payload.get("code", self._tr("chart.planet")))).strip())
        house = payload.get("house")
        sign = str(payload.get("sign", "")).strip()
        insight = str(payload.get("insight", "")).strip() or self._tr("chart.planet_insight_fallback")

        heading = f"{planet} {self._tr('chart.in_house')} {house}" if house else planet
        if sign:
            heading = f"{heading} ({sign})"
        self.chart_insight_label.setText(f"<b>{heading}</b><br>{insight}")

    def _handle_house_hovered(self, payload: Dict[str, Any]) -> None:
        house = payload.get("house")
        insight = str(payload.get("insight", "")).strip() or self._tr("chart.house_insight_fallback")
        self.chart_insight_label.setText(f"<b>{self._tr('chart.house')} {house}</b><br>{insight}")

    def _handle_house_clicked(self, house: int) -> None:
        self._handle_house_hovered(
            {
                "house": house,
                "insight": self.kundli_widget.get_house_insight(house),
            }
        )

    def _clear_chart_insight(self) -> None:
        self.chart_insight_label.setText(self._tr("ui.hover_chart_hint"))

    def _build_chart_insights(self, predictions: Any) -> Dict[str, Any]:
        by_planet: Dict[str, str] = {}
        by_house: Dict[int, str] = {}
        default_insight = ""

        for summary in self._prediction_summaries(predictions):
            normalized = summary.lower()
            mentioned_houses = self._extract_house_numbers(normalized)
            mentioned_planets = [
                row for row in self._latest_chart_data
                if str(row.get("Planet", "")).strip()
                and str(row.get("Planet", "")).strip().lower() in normalized
            ]

            short_summary = self._shorten_insight(summary)
            if not short_summary:
                continue

            if mentioned_planets and mentioned_houses:
                for row in mentioned_planets:
                    house = int(row.get("House", 0) or 0)
                    if house in mentioned_houses:
                        key = self._planet_insight_key(str(row.get("Planet", "")), house)
                        by_planet.setdefault(key, short_summary)
                        by_house.setdefault(house, short_summary)
            elif mentioned_houses:
                for house in mentioned_houses:
                    by_house.setdefault(house, short_summary)
            elif mentioned_planets:
                for row in mentioned_planets:
                    house = int(row.get("House", 0) or 0)
                    key = self._planet_insight_key(str(row.get("Planet", "")), house)
                    by_planet.setdefault(key, short_summary)
                    if house:
                        by_house.setdefault(house, short_summary)
            elif not default_insight:
                default_insight = short_summary

        if not default_insight:
            default_insight = self._tr("chart.insight_fallback")

        return {
            "by_planet": by_planet,
            "by_house": by_house,
            "default": default_insight,
        }

    def _prediction_summaries(self, predictions: Any) -> List[str]:
        summaries: List[str] = []

        if isinstance(predictions, dict):
            for details in predictions.values():
                summary = str(details.get("summary", "")).strip()
                if summary:
                    summaries.append(summary)
        else:
            for prediction in predictions:
                summary = str(prediction.get("text", "")).strip()
                if summary:
                    summaries.append(summary)

        return summaries

    def _localize_predictions(self, predictions: Any) -> Any:
        if isinstance(predictions, dict):
            localized: Dict[str, Dict[str, Any]] = {}
            for category, details in predictions.items():
                details_copy = dict(details or {})
                localized_summary = self._localized_summary_for_details(details_copy)
                if localized_summary:
                    details_copy["summary"] = localized_summary
                localized[category] = details_copy
            return localized

        localized_list = []
        for prediction in predictions:
            prediction_copy = dict(prediction or {})
            localized_text = self._translated_prediction_message(
                prediction_copy.get("result_key") or prediction_copy.get("text_key")
            )
            if localized_text:
                prediction_copy["text"] = localized_text
            localized_list.append(prediction_copy)
        return localized_list

    def _localized_summary_for_details(self, details: Dict[str, Any]) -> str:
        positive_text = self._join_prediction_messages(details.get("positive_summary_keys", []))
        negative_text = self._join_prediction_messages(details.get("negative_summary_keys", []))
        if not positive_text and not negative_text:
            return ""

        score = float(details.get("score", 0) or 0)
        if positive_text and negative_text:
            if score > 0:
                connector = self._tr("prediction.connector.however")
                return f"{positive_text} {connector} {negative_text}".strip()
            if score < 0:
                connector = self._tr("prediction.connector.still")
                return f"{negative_text} {connector} {positive_text}".strip()
            connector = self._tr("prediction.connector.at_same_time")
            return f"{positive_text} {connector} {negative_text}".strip()

        return positive_text or negative_text

    def _join_prediction_messages(self, keys: List[str]) -> str:
        messages = [self._translated_prediction_message(key) for key in keys]
        messages = [message for message in messages if message]
        return " ".join(messages)

    def _translated_prediction_message(self, key: Any) -> str:
        normalized = str(key or "").strip()
        if not normalized:
            return ""

        mapped_prediction = get_prediction(normalized, self.language_manager.current_language)
        if mapped_prediction:
            return mapped_prediction

        path = normalized if normalized.startswith("prediction.message.") else f"prediction.message.{normalized}"
        translated = self._tr(path)
        if translated == path:
            return ""
        return translated

    def _extract_house_numbers(self, normalized_summary: str) -> List[int]:
        house_numbers = []
        for match in re.findall(r"\b(\d{1,2})(?:st|nd|rd|th)\s+house\b", normalized_summary):
            house = int(match)
            if 1 <= house <= 12 and house not in house_numbers:
                house_numbers.append(house)
        return house_numbers

    def _planet_insight_key(self, planet_name: str, house: int) -> str:
        normalized_planet = re.sub(r"\s+", " ", str(planet_name or "").strip().lower())
        return f"{normalized_planet}|{int(house)}"

    def _shorten_insight(self, text: str, limit: int = 140) -> str:
        compact = re.sub(r"\s+", " ", str(text or "").strip())
        if len(compact) <= limit:
            return compact
        return compact[: limit - 3].rstrip() + "..."

    def _translate_planet_name(self, planet_name: str) -> str:
        normalized = re.sub(r"\s+", "_", str(planet_name or "").strip().lower())
        return self._tr(f"planet.{normalized}")
