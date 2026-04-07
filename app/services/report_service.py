from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.repositories.database_manager import DatabaseManager
from app.repositories.user_repo import UserRepository
from app.repositories.chart_repo import ChartRepository
from app.services.horoscope_service import HoroscopeService


class ReportService:
    """
    Generates offline horoscope PDF reports from existing service-layer outputs.

    Step 2 scope:
    - fetch report data from existing repositories/services
    - create a basic PDF shell
    - keep formatting logic isolated from UI code
    """

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.user_repo = UserRepository(db_manager)
        self.chart_repo = ChartRepository(db_manager)
        self.horoscope_service = HoroscopeService(db_manager)
        self.styles = self._build_styles()

    def generate_pdf(self, user_id: int, output_path: str) -> str:
        """
        Builds a structured horoscope PDF for the given user and returns the saved path.
        """
        report_data = self._fetch_report_data(user_id)
        destination = Path(output_path).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        chart_image_path = self._render_chart_to_png(report_data)

        try:
            doc = SimpleDocTemplate(
                str(destination),
                pagesize=A4,
                leftMargin=18 * mm,
                rightMargin=18 * mm,
                topMargin=18 * mm,
                bottomMargin=18 * mm,
                title="Horoscope Report",
                author="Offline Horoscope (Kundli) Engine",
            )
            story = []

            story.extend(self._build_header_section(report_data))
            story.extend(self._build_chart_section(chart_image_path))
            story.extend(self._build_predictions_section(report_data))
            story.extend(self._build_dasha_section(report_data))
            story.extend(self._build_key_events_section(report_data))

            doc.build(story)
        finally:
            if chart_image_path:
                try:
                    Path(chart_image_path).unlink(missing_ok=True)
                except OSError:
                    pass
        return str(destination)

    def _fetch_report_data(self, user_id: int) -> Dict[str, Any]:
        """Collects reusable report data from existing repositories and services."""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found.")

        chart_data = self.chart_repo.get_by_user_id(user_id)
        if not chart_data:
            raise ValueError("No chart data found for this user.")

        _, predictions = self.horoscope_service.load_chart_for_user(user_id)
        timeline_data = self.horoscope_service.get_timeline_data(user_id)

        return {
            "user": {
                "id": user.id,
                "name": user.name,
                "dob": user.dob,
                "tob": user.tob,
                "place": user.place,
                "latitude": user.latitude,
                "longitude": user.longitude,
            },
            "chart_data": [
                {
                    "planet_name": entry.planet_name,
                    "sign": entry.sign,
                    "house": entry.house,
                    "degree": entry.degree,
                }
                for entry in chart_data
            ],
            "predictions": predictions,
            "timeline": timeline_data,
        }

    def _build_styles(self):
        """Builds custom paragraph styles for a cleaner report layout."""
        styles = getSampleStyleSheet()
        styles.add(
            ParagraphStyle(
                name="ReportSubtitle",
                parent=styles["BodyText"],
                fontName="Helvetica",
                fontSize=10,
                leading=14,
                textColor=colors.HexColor("#475569"),
                spaceAfter=4 * mm,
            )
        )
        styles.add(
            ParagraphStyle(
                name="SectionTitle",
                parent=styles["Heading2"],
                fontName="Helvetica-Bold",
                fontSize=14,
                leading=18,
                textColor=colors.HexColor("#0f172a"),
                spaceAfter=2 * mm,
                borderPadding=0,
            )
        )
        styles.add(
            ParagraphStyle(
                name="SectionBody",
                parent=styles["BodyText"],
                fontName="Helvetica",
                fontSize=10,
                leading=14,
                textColor=colors.HexColor("#1f2937"),
                spaceAfter=2 * mm,
            )
        )
        styles.add(
            ParagraphStyle(
                name="MutedBody",
                parent=styles["BodyText"],
                fontName="Helvetica-Oblique",
                fontSize=9,
                leading=13,
                textColor=colors.HexColor("#64748b"),
                spaceAfter=2 * mm,
            )
        )
        styles.add(
            ParagraphStyle(
                name="PredictionCard",
                parent=styles["BodyText"],
                fontName="Helvetica",
                fontSize=10,
                leading=14,
                textColor=colors.HexColor("#0f172a"),
                borderWidth=0.7,
                borderColor=colors.HexColor("#dbe4f0"),
                borderPadding=8,
                backColor=colors.HexColor("#f8fafc"),
                spaceAfter=4 * mm,
            )
        )
        return styles

    def _build_header_section(self, report_data: Dict[str, Any]) -> list:
        """Builds the top header section with app title and user details."""
        user = report_data["user"]

        user_details = (
            f"<b>Name:</b> {user['name']}<br/>"
            f"<b>Date of Birth:</b> {user['dob']}<br/>"
            f"<b>Time of Birth:</b> {user['tob']}<br/>"
            f"<b>Place:</b> {user['place']}"
        )

        return [
            Paragraph("Offline Horoscope Report", self.styles["Title"]),
            Paragraph(
                "A structured summary of chart insights, prediction scores, and life timing indicators.",
                self.styles["ReportSubtitle"],
            ),
            Paragraph(user_details, self.styles["SectionBody"]),
            Spacer(1, 8 * mm),
        ]

    def _build_chart_section(self, chart_image_path: str | None) -> list:
        """Builds the Kundli chart section using a rendered PNG when available."""
        story = [Paragraph("Kundli Chart", self.styles["SectionTitle"]), Spacer(1, 2 * mm)]

        if chart_image_path and Path(chart_image_path).exists():
            chart_image = RLImage(chart_image_path, width=90 * mm, height=90 * mm)
            story.append(chart_image)
            story.append(Spacer(1, 4 * mm))
        else:
            story.append(
                Paragraph(
                    "Chart image could not be rendered in this environment. "
                    "The rest of the report remains available offline.",
                    self.styles["MutedBody"],
                )
            )
            story.append(Spacer(1, 4 * mm))

        return story + [Spacer(1, 4 * mm)]

    def _build_predictions_section(self, report_data: Dict[str, Any]) -> list:
        """Builds the scored prediction section for core categories."""
        story = [Paragraph("Predictions", self.styles["SectionTitle"]), Spacer(1, 2 * mm)]

        predictions = report_data.get("predictions", {})
        for category in ("career", "marriage", "finance"):
            details = predictions.get(
                category,
                {
                    "summary": "No strong indication available.",
                    "confidence": "low",
                },
            )
            text = (
                f"<b>{category.title()}</b><br/>"
                f"Summary: {details.get('summary', 'No summary available.')}<br/>"
                f"Confidence: {str(details.get('confidence', 'low')).title()}"
            )
            story.append(Paragraph(text, self.styles["PredictionCard"]))

        story.append(Spacer(1, 4 * mm))
        return story

    def _build_dasha_section(self, report_data: Dict[str, Any]) -> list:
        """Builds the Dasha timeline table section."""
        timeline_rows = report_data.get("timeline", {}).get("timeline", [])

        table_data = [["Planet", "Start", "End"]]
        for row in timeline_rows:
            table_data.append(
                [
                    row.get("planet", "Unknown"),
                    row.get("start", ""),
                    row.get("end", ""),
                ]
            )

        table = Table(table_data, colWidths=[40 * mm, 40 * mm, 40 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )

        return [
            Paragraph("Dasha Timeline", self.styles["SectionTitle"]),
            Spacer(1, 2 * mm),
            table,
            Spacer(1, 8 * mm),
        ]

    def _build_key_events_section(self, report_data: Dict[str, Any]) -> list:
        """Builds a compact section summarizing key career, marriage, and finance periods."""
        story = [Paragraph("Key Life Events", self.styles["SectionTitle"]), Spacer(1, 2 * mm)]

        timeline_rows = report_data.get("timeline", {}).get("timeline", [])
        category_labels = {
            "career": "Career growth periods",
            "marriage": "Marriage windows",
            "finance": "Financial peaks",
        }

        for category, label in category_labels.items():
            matching_periods = []
            for row in timeline_rows:
                events = row.get("events", [])
                if any(str(event.get("type", "")).strip().lower() == category for event in events):
                    matching_periods.append(
                        f"{row.get('planet', 'Unknown')} Mahadasha ({row.get('start', '')} to {row.get('end', '')})"
                    )

            if matching_periods:
                content = "<br/>".join(matching_periods)
            else:
                content = "No strong period identified."

            story.append(Paragraph(f"<b>{label}</b><br/>{content}", self.styles["SectionBody"]))
            story.append(Spacer(1, 4 * mm))

        return story

    def _render_chart_to_png(self, report_data: Dict[str, Any]) -> str | None:
        """Renders the existing Kundli widget to a temporary PNG file when PyQt is available."""
        try:
            from PyQt6.QtCore import Qt
            from PyQt6.QtGui import QColor, QImage, QPainter
            from PyQt6.QtWidgets import QApplication
            from app.ui.widgets.kundli_chart import KundliChart
        except Exception:
            return None

        app = QApplication.instance()
        owns_app = False
        if app is None:
            app = QApplication([])
            owns_app = True

        try:
            widget = KundliChart()
            widget.resize(480, 480)
            widget.update_chart(self._format_chart_for_widget(report_data.get("chart_data", [])))

            image = QImage(widget.size(), QImage.Format.Format_ARGB32)
            image.fill(QColor(Qt.GlobalColor.white))

            painter = QPainter(image)
            widget.render(painter)
            painter.end()

            temp_file = tempfile.NamedTemporaryFile(
                prefix="horoscope_chart_",
                suffix=".png",
                delete=False,
            )
            temp_path = Path(temp_file.name)
            temp_file.close()
            image.save(str(temp_path), "PNG")
            return str(temp_path)
        except Exception:
            return None
        finally:
            if owns_app and app is not None:
                app.quit()

    def _format_chart_for_widget(self, chart_data: list[dict]) -> list[dict]:
        """Converts repository chart data into the shape expected by the Kundli widget."""
        return [
            {
                "Planet": entry.get("planet_name", ""),
                "Sign": entry.get("sign", ""),
                "House": entry.get("house", 1),
                "Degree": entry.get("degree", 0.0),
            }
            for entry in chart_data
        ]
