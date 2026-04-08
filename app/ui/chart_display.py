from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from typing import List, Dict, Any, Optional
import re

class ChartDisplay(QWidget):
    generate_report_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        self.title_label = QLabel("Chart Information")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        from app.ui.widgets import ChartHeaderData, NorthIndianChartWidget

        self._chart_header_type = ChartHeaderData
        self.kundli_widget = NorthIndianChartWidget()
        self.kundli_widget.planet_hovered.connect(self._handle_planet_hovered)
        self.kundli_widget.house_hovered.connect(self._handle_house_hovered)
        self.kundli_widget.planet_clicked.connect(self._handle_planet_hovered)
        self.kundli_widget.house_clicked.connect(self._handle_house_clicked)
        self.kundli_widget.hover_cleared.connect(self._clear_chart_insight)
        self._latest_chart_data: List[Dict[str, Any]] = []
        
        self.predictions_label = QLabel("Predictions:")
        self.predictions_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 10px;")

        self.chart_insight_label = QLabel("Hover over a planet or house to view a quick insight.")
        self.chart_insight_label.setWordWrap(True)
        self.chart_insight_label.setStyleSheet(
            "background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; "
            "padding: 8px 10px; color: #334155; font-size: 12px;"
        )
        
        self.predictions_text = QLabel("Awaiting generation...")
        self.predictions_text.setWordWrap(True)

        self.report_button = QPushButton("Generate Report")
        self.report_button.setEnabled(False)
        self.report_button.clicked.connect(self.generate_report_requested.emit)

        layout.addWidget(self.title_label)
        layout.addWidget(self.kundli_widget)
        layout.addWidget(self.chart_insight_label)
        layout.addWidget(self.predictions_label)
        layout.addWidget(self.predictions_text)
        layout.addWidget(self.report_button)
        
        self.setLayout(layout)

    def display_chart(self, chart_data: List[Dict], header_data: Optional[Dict[str, str]] = None):
        """Renders chart rows and optional chart-header metadata."""
        self._latest_chart_data = list(chart_data)
        self.kundli_widget.set_chart_data(chart_data)

        if header_data:
            self.kundli_widget.set_header_data(
                self._chart_header_type(
                    title=str(header_data.get("title", "Birth Chart")),
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
            self.predictions_text.setText("No predictions found for this chart.")
            return

        html = "<ul>"
        if isinstance(predictions, dict):
            for category, details in predictions.items():
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
            for p in predictions:
                score_color = "#d9534f" if p["score"] > 50 else "#5bc0de" if p["score"] > 20 else "#777"
                html += f"<li style='margin-bottom: 5px;'>"
                html += f"<span style='color: white; background-color: {score_color}; border-radius: 3px; padding: 2px 4px; font-size: 10px; margin-right: 5px;'>"
                html += f"{p['category'].upper()} | {p['score']}</span> "
                html += f"{p['text']}</li>"
        html += "</ul>"

        self.kundli_widget.set_insights(**self._build_chart_insights(predictions))
        self.predictions_text.setText(html)

    def _handle_planet_hovered(self, payload: Dict[str, Any]) -> None:
        planet = str(payload.get("planet", payload.get("code", "Planet"))).strip()
        house = payload.get("house")
        sign = str(payload.get("sign", "")).strip()
        insight = str(payload.get("insight", "")).strip() or "No specific insight available for this placement yet."

        heading = f"{planet} in House {house}" if house else planet
        if sign:
            heading = f"{heading} ({sign})"
        self.chart_insight_label.setText(f"<b>{heading}</b><br>{insight}")

    def _handle_house_hovered(self, payload: Dict[str, Any]) -> None:
        house = payload.get("house")
        insight = str(payload.get("insight", "")).strip() or "No specific insight available for this house yet."
        self.chart_insight_label.setText(f"<b>House {house}</b><br>{insight}")

    def _handle_house_clicked(self, house: int) -> None:
        self._handle_house_hovered(
            {
                "house": house,
                "insight": self.kundli_widget.get_house_insight(house),
            }
        )

    def _clear_chart_insight(self) -> None:
        self.chart_insight_label.setText("Hover over a planet or house to view a quick insight.")

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
            default_insight = "Hover or click to inspect chart placements."

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
