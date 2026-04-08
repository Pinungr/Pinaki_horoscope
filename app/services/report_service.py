from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.repositories.chart_repo import ChartRepository
from app.repositories.database_manager import DatabaseManager
from app.repositories.user_repo import UserRepository
from app.services.app_settings_service import AppSettingsService
from app.services.astrology_advanced_service import AstrologyAdvancedService
from app.services.event_service import EventService
from app.services.horoscope_service import HoroscopeService
from app.services.language_manager import LanguageManager
from app.services.reasoning_service import ReasoningService
from app.services.timeline_service import TimelineService


class ReportService:
    """Generates offline horoscope PDF reports from existing service-layer outputs."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.user_repo = UserRepository(db_manager)
        self.chart_repo = ChartRepository(db_manager)
        self.horoscope_service = HoroscopeService(db_manager)
        self.settings_service = AppSettingsService()
        self.advanced_service = AstrologyAdvancedService()
        self.timeline_service = TimelineService()
        self.reasoning_service = ReasoningService()
        self.event_service = EventService()
        self.styles = self._build_styles()
        self._language_manager = LanguageManager("en")

    def generate_pdf(self, user_id: int, output_path: str, *, language: str = "en") -> str:
        """Builds a structured horoscope PDF for the given user and returns the saved path."""
        normalized_language = self._normalize_language(language)
        self._language_manager = LanguageManager(normalized_language)
        report_data = self._fetch_report_data(user_id, language=normalized_language)
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
                title=self._tr("report.meta.document_title", "Horoscope Report"),
                author=self._tr("report.meta.document_author", "Offline Horoscope (Kundli) Engine"),
            )
            story = []

            story.extend(self._build_header_section(report_data))
            story.extend(self._build_chart_section(chart_image_path))
            story.extend(self._build_top_insights_section(report_data))
            story.extend(self._build_predictions_section(report_data))
            story.extend(self._build_timeline_forecast_section(report_data))
            story.extend(self._build_key_events_section(report_data))
            story.extend(self._build_reasoning_summary_section(report_data))
            story.extend(self._build_dasha_section(report_data))

            doc.build(story)
        finally:
            if chart_image_path:
                try:
                    Path(chart_image_path).unlink(missing_ok=True)
                except OSError:
                    pass
        return str(destination)

    def _fetch_report_data(self, user_id: int, *, language: str = "en") -> Dict[str, Any]:
        """Collects reusable report data from existing repositories and services."""
        user = self.user_repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found.")

        chart_data = self.chart_repo.get_by_user_id(user_id)
        if not chart_data:
            raise ValueError("No chart data found for this user.")

        _, predictions = self.horoscope_service.load_chart_for_user(user_id)
        timeline_data = self.horoscope_service.get_timeline_data(user_id, language=language)

        unified_summary: Dict[str, Any] = {}
        unified_predictions: list[dict[str, Any]] = []
        timeline_forecast: Dict[str, Any] = {"timeline": []}
        reasoning_rows: list[dict[str, Any]] = []
        key_events: Dict[str, Dict[str, Any]] = {}

        import logging as _logging
        _rlog = _logging.getLogger(__name__)

        # ── 1. Advanced data ──────────────────────────────────────────────────
        advanced_data: Dict[str, Any] = {}
        try:
            advanced_data = self.advanced_service.generate_advanced_data(
                chart_data,
                user.dob,
                language=language,
            )
            unified_payload = advanced_data.get("unified", {}) if isinstance(advanced_data, dict) else {}
            if isinstance(unified_payload, dict):
                unified_summary = dict(unified_payload.get("summary", {}) or {})
                raw_predictions = unified_payload.get("predictions", [])
                if isinstance(raw_predictions, list):
                    unified_predictions = [dict(row) for row in raw_predictions if isinstance(row, dict)]
        except Exception as exc:
            _rlog.warning("ReportService: advanced data generation failed — unified/timeline sections will be empty: %s", exc)

        # ── 2. Timeline forecast ──────────────────────────────────────────────
        dasha_timeline = advanced_data.get("dasha", []) if isinstance(advanced_data, dict) else []
        try:
            timeline_forecast = self.timeline_service.build_timeline_forecast(
                unified_predictions,
                dasha_timeline,
                language=language,
            )
        except Exception as exc:
            _rlog.warning("ReportService: timeline forecast failed — timeline section will be empty: %s", exc)

        # ── 3. Reasoning ──────────────────────────────────────────────────────
        try:
            reasoning_rows = self.reasoning_service.generate_explanations(
                unified_predictions,
                language=language,
            )
        except Exception as exc:
            _rlog.warning("ReportService: reasoning generation failed — reasoning section will be empty: %s", exc)

        # ── 4. Key events ─────────────────────────────────────────────────────
        try:
            for area in ("career", "marriage", "finance"):
                event_result = self.event_service.predict_event(
                    user_query=area,
                    predictions=unified_predictions,
                    timeline_data=timeline_forecast,
                    reasoning_data=reasoning_rows,
                    language=language,
                )
                if isinstance(event_result, dict):
                    key_events[area] = event_result
        except Exception as exc:
            _rlog.warning("ReportService: key events generation failed — key events section will be empty: %s", exc)



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
            "unified_summary": unified_summary,
            "unified_predictions": unified_predictions,
            "timeline_forecast": timeline_forecast,
            "reasoning": reasoning_rows,
            "key_events": key_events,
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
        styles.add(
            ParagraphStyle(
                name="InsightCard",
                parent=styles["BodyText"],
                fontName="Helvetica",
                fontSize=10,
                leading=14,
                textColor=colors.HexColor("#0f172a"),
                borderWidth=0.7,
                borderColor=colors.HexColor("#d1fae5"),
                borderPadding=8,
                backColor=colors.HexColor("#f0fdf4"),
                spaceAfter=3 * mm,
            )
        )
        return styles

    def _build_header_section(self, report_data: Dict[str, Any]) -> list:
        """Builds the top header section with app title and user details."""
        user = report_data["user"]

        user_details = (
            f"<b>{escape(self._tr('report.labels.name', 'Name'))}:</b> {escape(str(user['name']))}<br/>"
            f"<b>{escape(self._tr('report.labels.date_of_birth', 'Date of Birth'))}:</b> {escape(str(user['dob']))}<br/>"
            f"<b>{escape(self._tr('report.labels.time_of_birth', 'Time of Birth'))}:</b> {escape(str(user['tob']))}<br/>"
            f"<b>{escape(self._tr('report.labels.place', 'Place'))}:</b> {escape(str(user['place']))}"
        )

        return [
            Paragraph(self._tr("report.sections.offline_horoscope_report", "Offline Horoscope Report"), self.styles["Title"]),
            Paragraph(
                self._tr(
                    "report.sections.subtitle",
                    "A structured summary of chart insights, prediction scores, and life timing indicators.",
                ),
                self.styles["ReportSubtitle"],
            ),
            Paragraph(user_details, self.styles["SectionBody"]),
            Spacer(1, 8 * mm),
        ]

    def _build_chart_section(self, chart_image_path: str | None) -> list:
        """Builds the Kundli chart section using a rendered PNG when available."""
        story = [
            Paragraph(self._tr("report.sections.kundli_chart", "Kundli Chart"), self.styles["SectionTitle"]),
            Spacer(1, 2 * mm),
        ]

        if chart_image_path and Path(chart_image_path).exists():
            chart_image = RLImage(chart_image_path, width=90 * mm, height=90 * mm)
            story.append(chart_image)
            story.append(Spacer(1, 4 * mm))
        else:
            story.append(
                Paragraph(
                    self._tr(
                        "report.messages.chart_unavailable",
                        "Chart image could not be rendered in this environment. The rest of the report remains available offline.",
                    ),
                    self.styles["MutedBody"],
                )
            )
            story.append(Spacer(1, 4 * mm))

        return story + [Spacer(1, 4 * mm)]

    def _build_top_insights_section(self, report_data: Dict[str, Any]) -> list:
        """Builds a concise top-insights summary with confidence and focus areas."""
        summary = report_data.get("unified_summary", {})
        if not isinstance(summary, dict):
            summary = {}

        top_areas = summary.get("top_areas", []) if isinstance(summary.get("top_areas"), list) else []
        top_areas = [self._normalize_area(area) for area in top_areas if str(area or "").strip()]

        time_focus = summary.get("time_focus", []) if isinstance(summary.get("time_focus"), list) else []
        time_focus = [self._normalize_area(area) for area in time_focus if str(area or "").strip()]

        confidence_score = self._safe_int(summary.get("confidence_score"))
        confidence_band = (
            self._tr("report.values.confidence_high", "High")
            if confidence_score >= 80
            else self._tr("report.values.confidence_medium", "Medium")
            if confidence_score >= 50
            else self._tr("report.values.confidence_low", "Low")
        )

        story = [
            Paragraph(self._tr("report.sections.top_insights", "Top Insights"), self.styles["SectionTitle"]),
            Spacer(1, 2 * mm),
        ]

        no_data = self._tr("report.values.not_enough_data_yet", "Not enough data yet")
        no_timing = self._tr("report.values.no_immediate_timing_hotspot", "No immediate timing hotspot")
        overall_confidence_label = self._tr("report.labels.overall_confidence", "Overall Confidence")
        top_areas_label = self._tr("report.labels.top_areas", "Top Areas")
        time_focus_label = self._tr("report.labels.time_focus", "Time Focus")

        body = (
            f"<b>{escape(overall_confidence_label)}:</b> {confidence_score}% ({escape(confidence_band)})<br/>"
            f"<b>{escape(top_areas_label)}:</b> {', '.join(area.title() for area in top_areas) if top_areas else escape(no_data)}<br/>"
            f"<b>{escape(time_focus_label)}:</b> {', '.join(area.title() for area in time_focus) if time_focus else escape(no_timing)}"
        )
        story.append(Paragraph(body, self.styles["InsightCard"]))
        story.append(Spacer(1, 4 * mm))
        return story

    def _build_predictions_section(self, report_data: Dict[str, Any]) -> list:
        """Builds the prediction section using unified predictions when available."""
        story = [
            Paragraph(self._tr("report.sections.predictions", "Predictions"), self.styles["SectionTitle"]),
            Spacer(1, 2 * mm),
        ]

        unified_predictions = report_data.get("unified_predictions", [])
        if isinstance(unified_predictions, list) and unified_predictions:
            sorted_predictions = sorted(
                [row for row in unified_predictions if isinstance(row, dict)],
                key=lambda row: self._safe_int(row.get("score")),
                reverse=True,
            )
            for row in sorted_predictions[:6]:
                area = self._normalize_area(row.get("area", "general")).title()
                yoga = escape(str(row.get("yoga", "Yoga")))
                strength = escape(str(row.get("strength", self._tr("report.values.medium", "medium"))).title())
                score = self._safe_int(row.get("score"))
                text = escape(
                    str(
                        row.get("refined_text")
                        or row.get("text")
                        or self._tr("report.values.no_summary_available", "No summary available.")
                    )
                )

                timing = row.get("timing", {}) if isinstance(row.get("timing"), dict) else {}
                maha = escape(str(timing.get("mahadasha", "")))
                antar = escape(str(timing.get("antardasha", "")))
                relevance = escape(str(timing.get("relevance", self._tr("report.values.low", "low"))).title())

                timing_label = self._tr("report.labels.timing", "Timing")
                timing_line = f"{timing_label}: {self._tr('report.values.no_specific_dasha_activation', 'No specific dasha activation.')}"
                if maha and antar:
                    timing_line = (
                        f"{timing_label}: {maha} {self._tr('report.values.mahadasha', 'Mahadasha')} / "
                        f"{antar} {self._tr('report.values.antardasha', 'Antardasha')} ({relevance})."
                    )
                elif maha:
                    timing_line = f"{timing_label}: {maha} {self._tr('report.values.mahadasha', 'Mahadasha')} ({relevance})."

                card_text = (
                    f"<b>{area} | {yoga}</b><br/>"
                    f"{escape(self._tr('report.labels.strength', 'Strength'))}: {strength} | "
                    f"{escape(self._tr('report.labels.score', 'Score'))}: {score}<br/>"
                    f"{text}<br/>"
                    f"<i>{timing_line}</i>"
                )
                story.append(Paragraph(card_text, self.styles["PredictionCard"]))

            story.append(Spacer(1, 4 * mm))
            return story

        predictions = report_data.get("predictions", {})
        for category in ("career", "marriage", "finance"):
            details = predictions.get(
                category,
                {
                    "summary": self._tr("report.values.no_strong_indication", "No strong indication available."),
                    "confidence": self._tr("report.values.low", "low"),
                },
            )
            text = (
                f"<b>{escape(category.title())}</b><br/>"
                f"{escape(self._tr('report.labels.summary', 'Summary'))}: "
                f"{escape(str(details.get('summary', self._tr('report.values.no_summary_available', 'No summary available.'))))}<br/>"
                f"{escape(self._tr('report.labels.confidence', 'Confidence'))}: "
                f"{escape(str(details.get('confidence', self._tr('report.values.low', 'low'))).title())}"
            )
            story.append(Paragraph(text, self.styles["PredictionCard"]))

        story.append(Spacer(1, 4 * mm))
        return story

    def _build_timeline_forecast_section(self, report_data: Dict[str, Any]) -> list:
        """Builds a year-wise timeline table from forecast rows."""
        story = [
            Paragraph(self._tr("report.sections.timeline_forecast", "Timeline Forecast"), self.styles["SectionTitle"]),
            Spacer(1, 2 * mm),
        ]

        forecast_rows = report_data.get("timeline_forecast", {}).get("timeline", [])
        if not isinstance(forecast_rows, list) or not forecast_rows:
            story.append(
                Paragraph(
                    self._tr("report.messages.no_forecast_rows", "No forecast timeline rows are available yet."),
                    self.styles["MutedBody"],
                )
            )
            story.append(Spacer(1, 4 * mm))
            return story

        table_data = [[
            self._tr("report.labels.period", "Period"),
            self._tr("report.labels.area", "Area"),
            self._tr("report.labels.event", "Event"),
            self._tr("report.labels.confidence", "Confidence"),
        ]]
        for row in forecast_rows[:12]:
            event_text = str(row.get("event", "")).strip() or self._tr("report.values.no_event_summary", "No event summary")
            if len(event_text) > 62:
                event_text = event_text[:59].rstrip() + "..."
            table_data.append(
                [
                    str(row.get("period", "Upcoming")),
                    self._normalize_area(row.get("area", "general")).title(),
                    event_text,
                    str(self._safe_int(row.get("confidence"))),
                ]
            )

        table = Table(table_data, colWidths=[28 * mm, 24 * mm, 86 * mm, 22 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e0f2fe")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bfdbfe")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ]
            )
        )

        story.extend([table, Spacer(1, 6 * mm)])
        return story

    def _build_dasha_section(self, report_data: Dict[str, Any]) -> list:
        """Builds the Dasha timeline table section."""
        timeline_rows = report_data.get("timeline", {}).get("timeline", [])
        if not isinstance(timeline_rows, list):
            timeline_rows = []

        table_data = [[
            self._tr("report.labels.planet", "Planet"),
            self._tr("report.labels.start", "Start"),
            self._tr("report.labels.end", "End"),
        ]]
        for row in timeline_rows[:18]:
            table_data.append(
                [
                    str(row.get("planet", self._tr("report.values.unknown", "Unknown"))),
                    str(row.get("start", "")),
                    str(row.get("end", "")),
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
            Paragraph(self._tr("report.sections.dasha_timeline", "Dasha Timeline"), self.styles["SectionTitle"]),
            Spacer(1, 2 * mm),
            table,
            Spacer(1, 8 * mm),
        ]

    def _build_key_events_section(self, report_data: Dict[str, Any]) -> list:
        """Builds key event highlights for core life areas."""
        story = [
            Paragraph(self._tr("report.sections.key_life_events", "Key Life Events"), self.styles["SectionTitle"]),
            Spacer(1, 2 * mm),
        ]

        key_events = report_data.get("key_events", {})
        if not isinstance(key_events, dict):
            key_events = {}

        forecast_rows = report_data.get("timeline_forecast", {}).get("timeline", [])
        if not isinstance(forecast_rows, list):
            forecast_rows = []

        category_labels = {
            "career": self._tr("report.values.career", "Career"),
            "marriage": self._tr("report.values.marriage", "Marriage"),
            "finance": self._tr("report.values.finance", "Finance"),
        }

        for area, label in category_labels.items():
            area_event = key_events.get(area, {}) if isinstance(key_events.get(area), dict) else {}

            if area_event.get("answer"):
                supporting_events = area_event.get("supporting_events", [])
                first_event = supporting_events[0] if isinstance(supporting_events, list) and supporting_events else {}
                period = str(first_event.get("period", self._tr("report.values.upcoming", "Upcoming"))).strip() or self._tr("report.values.upcoming", "Upcoming")
                confidence = self._safe_int(area_event.get("confidence"))
                content = (
                    f"{escape(str(area_event.get('answer', '')))}<br/>"
                    f"{escape(self._tr('report.labels.window', 'Window'))}: {escape(period)} | "
                    f"{escape(self._tr('report.labels.confidence', 'Confidence'))}: {confidence}"
                )
            else:
                fallback = next(
                    (
                        row for row in forecast_rows
                        if self._normalize_area(row.get("area", "general")) == area
                    ),
                    None,
                )
                if fallback:
                    content = (
                        f"{escape(str(fallback.get('event', self._tr('report.values.notable_development', 'Notable development'))))}<br/>"
                        f"{escape(self._tr('report.labels.window', 'Window'))}: "
                        f"{escape(str(fallback.get('period', self._tr('report.values.upcoming', 'Upcoming'))))} | "
                        f"{escape(self._tr('report.labels.confidence', 'Confidence'))}: "
                        f"{self._safe_int(fallback.get('confidence'))}"
                    )
                else:
                    content = self._tr("report.values.no_strong_period", "No strong period identified.")

            story.append(Paragraph(f"<b>{escape(label)}</b><br/>{content}", self.styles["SectionBody"]))
            story.append(Spacer(1, 3 * mm))

        story.append(Spacer(1, 3 * mm))
        return story

    def _build_reasoning_summary_section(self, report_data: Dict[str, Any]) -> list:
        """Builds concise reasoning cards from the reasoning engine output."""
        story = [
            Paragraph(self._tr("report.sections.reasoning_summary", "Reasoning Summary"), self.styles["SectionTitle"]),
            Spacer(1, 2 * mm),
        ]

        reasoning_rows = report_data.get("reasoning", [])
        if not isinstance(reasoning_rows, list) or not reasoning_rows:
            story.append(
                Paragraph(
                    self._tr("report.messages.reasoning_unavailable", "Reasoning details are not available yet."),
                    self.styles["MutedBody"],
                )
            )
            story.append(Spacer(1, 4 * mm))
            return story

        for row in reasoning_rows[:6]:
            if not isinstance(row, dict):
                continue
            area = self._normalize_area(row.get("area", "general")).title()
            explanation = escape(
                str(row.get("explanation", self._tr("report.values.no_explanation_available", "No explanation available.")))
            )
            factors = row.get("supporting_factors", [])
            if isinstance(factors, list):
                factor_text = "; ".join(escape(str(item)) for item in factors[:4] if str(item or "").strip())
            else:
                factor_text = ""

            text = f"<b>{escape(area)}</b><br/>{explanation}"
            if factor_text:
                text += (
                    f"<br/><i>{escape(self._tr('report.labels.supporting_factors', 'Supporting factors'))}:</i> "
                    f"{factor_text}"
                )
            story.append(Paragraph(text, self.styles["PredictionCard"]))

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

    def _tr(self, key: str, default: str) -> str:
        value = self._language_manager.get_text(key)
        if value == key:
            return default
        return value

    def _normalize_language(self, language: str) -> str:
        normalized = str(language or "").strip().lower()
        if not normalized:
            settings = self.settings_service.load()
            normalized = str(settings.get("language_code", "en")).strip().lower() or "en"
        if normalized not in {"en", "hi", "or"}:
            return "en"
        return normalized

    @staticmethod
    def _normalize_area(area: Any) -> str:
        normalized = str(area or "general").strip().lower() or "general"
        if normalized in {"wealth", "financial"}:
            return "finance"
        return normalized

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(round(float(value)))
        except (TypeError, ValueError):
            return 0
