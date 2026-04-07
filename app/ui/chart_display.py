from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView
from typing import List, Dict

class ChartDisplay(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        self.title_label = QLabel("Chart Information")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        
        # Replace the literal table with our graphical widget
        from app.ui.widgets.kundli_chart import KundliChart
        self.kundli_widget = KundliChart()
        
        self.predictions_label = QLabel("Predictions:")
        self.predictions_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 10px;")
        
        self.predictions_text = QLabel("Awaiting generation...")
        self.predictions_text.setWordWrap(True)

        layout.addWidget(self.title_label)
        layout.addWidget(self.kundli_widget)
        layout.addWidget(self.predictions_label)
        layout.addWidget(self.predictions_text)
        
        self.setLayout(layout)

    def display_chart(self, chart_data: List[Dict]):
        """Pass the dictionary data strictly to the visual map representation."""
        self.kundli_widget.update_chart(chart_data)

    def display_predictions(self, predictions: List[Dict]):
        """Show matching rules/predictions as scored categories."""
        if not predictions:
            self.predictions_text.setText("No predictions found for this chart.")
            return
            
        html = "<ul>"
        for p in predictions:
            score_color = "#d9534f" if p["score"] > 50 else "#5bc0de" if p["score"] > 20 else "#777"
            html += f"<li style='margin-bottom: 5px;'>"
            html += f"<span style='color: white; background-color: {score_color}; border-radius: 3px; padding: 2px 4px; font-size: 10px; margin-right: 5px;'>"
            html += f"{p['category'].upper()} | {p['score']}</span> "
            html += f"{p['text']}</li>"
        html += "</ul>"
        
        self.predictions_text.setText(html)
