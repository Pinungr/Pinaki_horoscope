from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from typing import List, Dict, Any, Optional

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
        
        self.predictions_label = QLabel("Predictions:")
        self.predictions_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 10px;")
        
        self.predictions_text = QLabel("Awaiting generation...")
        self.predictions_text.setWordWrap(True)

        self.report_button = QPushButton("Generate Report")
        self.report_button.setEnabled(False)
        self.report_button.clicked.connect(self.generate_report_requested.emit)

        layout.addWidget(self.title_label)
        layout.addWidget(self.kundli_widget)
        layout.addWidget(self.predictions_label)
        layout.addWidget(self.predictions_text)
        layout.addWidget(self.report_button)
        
        self.setLayout(layout)

    def display_chart(self, chart_data: List[Dict], header_data: Optional[Dict[str, str]] = None):
        """Renders chart rows and optional chart-header metadata."""
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

        self.report_button.setEnabled(bool(chart_data))

    def display_predictions(self, predictions: Any):
        """Show structured scored predictions without breaking older list-based payloads."""
        if not predictions:
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
        
        self.predictions_text.setText(html)
