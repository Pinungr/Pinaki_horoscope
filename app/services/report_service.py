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
            story.extend(self._build_shadbala_section(report_data))
            story.extend(self._build_transits_section(report_data))
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
        transits_data: Dict[str, Any] = {}
        shadbala_data: Dict[str, Any] = {}
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
            transits_data = dict(advanced_data.get("transits", {}) or {})
            shadbala_data = dict(advanced_data.get("shadbala", {}) or {})
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
            advanced_forecast = advanced_data.get("timeline_forecast", {}) if isinstance(advanced_data, dict) else {}
            if isinstance(advanced_forecast, dict) and isinstance(advanced_forecast.get("timeline"), list):
                timeline_forecast = advanced_forecast
            else:
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
            "transits": transits_data,
            "shadbala": shadbala_data,
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
                area = escape(self._normalize_area(row.get("area", "general")).title())
                yoga = escape(str(row.get("yoga", "Yoga")))
                score = self._safe_int(row.get("score"))

                confidence_label = str(row.get("confidence", "")).strip().title()
                title_bits = [area]
                if yoga:
                    title_bits.append(yoga)
                header_text = " | ".join(title_bits)
                if confidence_label:
                    header_text += f" | {escape(self._tr('report.labels.confidence', 'Confidence'))} {escape(confidence_label)}"
                header_text += f" | {escape(self._tr('report.labels.score', 'Score'))} {score}"

                narrative = self._extract_parashari_sections(row)
                section_html = [
                    self._format_report_subsection(
                        self._tr("report.labels.why_this_is_predicted", "Why this is predicted"),
                        narrative["promise"],
                    ),
                    self._format_report_subsection(
                        self._tr("report.labels.strength_of_indication", "Strength of indication"),
                        narrative["strength"],
                    ),
                    self._format_report_subsection(
                        self._tr("report.labels.when_it_may_manifest", "When it may manifest"),
                        narrative["timing"],
                    ),
                    self._format_report_subsection(
                        self._tr("report.labels.caution_and_limitations", "Caution & limitations"),
                        narrative["caution"],
                    ),
                ]

                reasoning_sections = [
                    (
                        self._tr("report.labels.strength_explanation", "Strength explanation"),
                        self._build_strength_reasoning_line(row),
                    ),
                    (
                        self._tr("report.labels.dasha_activation", "Dasha activation"),
                        self._build_dasha_reasoning_line(row),
                    ),
                    (
                        self._tr("report.labels.transit_trigger", "Transit trigger"),
                        self._build_transit_reasoning_line(row),
                    ),
                    (
                        self._tr("report.labels.conflict_resolution", "Conflict resolution"),
                        self._build_conflict_reasoning_line(row),
                    ),
                    (
                        self._tr("report.labels.concordance_summary", "Concordance summary"),
                        self._build_concordance_reasoning_line(row),
                    ),
                ]
                reasoning_html = "<br/>".join(
                    f"<i>{escape(label)}:</i> {escape(text)}"
                    for label, text in reasoning_sections
                    if str(text).strip()
                )

                card_text = f"<b>{header_text}</b><br/>{'<br/>'.join(section_html)}"
                if reasoning_html:
                    card_text += (
                        f"<br/><b>{escape(self._tr('report.labels.reasoning_details', 'Reasoning details'))}</b><br/>"
                        f"{reasoning_html}"
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

    def _extract_parashari_sections(self, row: Dict[str, Any]) -> Dict[str, str]:
        labels = {
            "promise": self._tr("prediction.parashari.labels.promise", "Promise"),
            "strength": self._tr("prediction.parashari.labels.strength", "Strength"),
            "timing": self._tr("prediction.parashari.labels.timing", "Timing"),
            "caution": self._tr("prediction.parashari.labels.caution", "Caution"),
        }
        sections: Dict[str, str] = {}
        for key in ("promise", "strength", "timing", "caution"):
            raw = str(row.get(f"{key}_text", "")).strip()
            sections[key] = self._strip_labeled_prefix(raw, labels[key]) if raw else ""

        final_narrative = str(row.get("final_narrative", "")).strip()
        if final_narrative:
            parsed = self._parse_parashari_narrative(final_narrative, labels)
            for key, value in parsed.items():
                if not sections.get(key) and value:
                    sections[key] = value

        if not sections["promise"]:
            sections["promise"] = str(
                row.get("final_prediction")
                or row.get("prediction")
                or row.get("text")
                or row.get("refined_text")
                or self._tr("report.values.no_summary_available", "No summary available.")
            ).strip()

        if not sections["strength"]:
            sections["strength"] = self._build_strength_reasoning_line(row)
        if not sections["timing"]:
            sections["timing"] = self._build_dasha_reasoning_line(row)
        if not sections["caution"]:
            sections["caution"] = self._build_conflict_reasoning_line(row)

        for key in sections:
            sections[key] = self._ensure_terminal_punctuation(sections[key])
        return sections

    @staticmethod
    def _format_report_subsection(title: str, body: str) -> str:
        heading = escape(str(title or "").strip())
        text = escape(str(body or "").strip())
        return f"<b>{heading}</b><br/>{text}"

    def _build_strength_reasoning_line(self, row: Dict[str, Any]) -> str:
        lines: list[str] = []
        strength = str(row.get("strength", "")).strip().lower()
        if strength:
            score = row.get("strength_score")
            if score is not None:
                lines.append(f"Strength is {strength} ({self._safe_int(score)}).")
            else:
                lines.append(f"Strength is {strength}.")

        strength_gate = row.get("strength_gate")
        if isinstance(strength_gate, dict):
            status = str(strength_gate.get("status", "")).strip().lower()
            if status:
                lines.append(f"Strength gate status: {status}.")

        agreement = str(row.get("agreement_level", "")).strip().lower()
        concordance_score = row.get("concordance_score")
        if agreement and concordance_score is not None:
            lines.append(f"Varga concordance is {agreement} ({concordance_score}).")
        elif agreement:
            lines.append(f"Varga concordance is {agreement}.")

        trace = row.get("trace")
        if isinstance(trace, dict):
            strength_trace = trace.get("strength")
            if isinstance(strength_trace, dict):
                weighted = strength_trace.get("weighted_contribution")
                if weighted is not None:
                    lines.append(f"Weighted bala contribution: {weighted}.")

        karaka_impact = row.get("karaka_impact")
        if isinstance(karaka_impact, list):
            snippets = [str(item).strip() for item in karaka_impact if str(item).strip()]
            if snippets:
                lines.append("; ".join(snippets[:2]) + ".")

        return self._finalize_reasoning_line(lines, self._tr("report.values.no_strength_reasoning", "Strength details are not available."))

    def _build_dasha_reasoning_line(self, row: Dict[str, Any]) -> str:
        lines: list[str] = []
        timing = row.get("timing")
        if not isinstance(timing, dict):
            timing = {}

        mahadasha = str(timing.get("mahadasha", "")).strip()
        antardasha = str(timing.get("antardasha", "")).strip()
        activation_label = self._resolve_activation_code(
            row.get("activation_label", timing.get("activation_level", timing.get("relevance", "")))
        )
        if mahadasha and antardasha:
            lines.append(
                f"{mahadasha} {self._tr('report.values.mahadasha', 'Mahadasha')} with "
                f"{antardasha} {self._tr('report.values.antardasha', 'Antardasha')}."
            )
        elif mahadasha:
            lines.append(f"{mahadasha} {self._tr('report.values.mahadasha', 'Mahadasha')}.")

        if activation_label:
            lines.append(f"Activation status: {self._format_activation_label(activation_label)}.")

        activation_score = row.get("activation_score", timing.get("activation_score"))
        if activation_score is not None:
            lines.append(f"Activation score: {self._safe_int(activation_score)}.")

        dasha_evidence = row.get("dasha_evidence", timing.get("dasha_evidence", []))
        evidence_line = self._format_source_factor_line(dasha_evidence, max_length=140, fallback_when_missing=False)
        if evidence_line:
            lines.append(evidence_line)

        return self._finalize_reasoning_line(lines, self._tr("report.values.no_dasha_reasoning", "Dasha details are not available."))

    def _build_transit_reasoning_line(self, row: Dict[str, Any]) -> str:
        lines: list[str] = []
        transit = row.get("transit")
        if not isinstance(transit, dict):
            transit = {}

        support_state = str(
            transit.get("support_state", row.get("transit_support_state", ""))
        ).strip().lower()
        trigger_level = str(transit.get("trigger_level", "")).strip().lower()
        if support_state:
            lines.append(f"Transit support is {support_state}.")
        if trigger_level:
            lines.append(f"Transit trigger level is {trigger_level}.")

        source_factors = transit.get("source_factors")
        if isinstance(source_factors, list):
            snippets = [str(item).strip() for item in source_factors if str(item).strip()]
            if snippets:
                lines.append("; ".join(snippets[:2]) + ".")

        return self._finalize_reasoning_line(lines, self._tr("report.values.no_transit_reasoning", "Transit details are not available."))

    def _build_conflict_reasoning_line(self, row: Dict[str, Any]) -> str:
        lines: list[str] = []
        resolution = row.get("resolution")
        if not isinstance(resolution, dict):
            resolution = {}

        dominant_outcome = str(row.get("dominant_outcome", resolution.get("dominant_outcome", ""))).strip().lower()
        if dominant_outcome:
            lines.append(f"Conflict outcome is {dominant_outcome}.")

        dominant_factor = str(resolution.get("dominant_factor", row.get("dominant_factor", ""))).strip().lower()
        if dominant_factor:
            template = self._tr("prediction.parashari.conflict.dominant_factor", "dominant factor: {dominant_factor}")
            lines.append(str(template).replace("{dominant_factor}", dominant_factor))

        dominant_reasoning = str(row.get("dominant_reasoning", resolution.get("dominant_reasoning", ""))).strip()
        resolution_explanation = str(
            row.get("resolution_explanation", resolution.get("resolution_explanation", ""))
        ).strip()
        if dominant_reasoning:
            lines.append(dominant_reasoning)
        elif resolution_explanation:
            lines.append(resolution_explanation)

        suppressed = row.get("suppressed_signals", row.get("suppressed_factors", resolution.get("suppressed_factors", [])))
        if isinstance(suppressed, list):
            factors: list[str] = []
            for entry in suppressed:
                if isinstance(entry, dict):
                    factor = str(entry.get("factor", "")).strip()
                    reason = str(entry.get("reason", "")).strip()
                    if factor and reason:
                        factors.append(f"{factor} ({reason})")
                    elif factor:
                        factors.append(factor)
                else:
                    text = str(entry).strip()
                    if text:
                        factors.append(text)
            if factors:
                template = self._tr("prediction.parashari.conflict.suppressed_influence", "suppressed influence: {suppressed}")
                lines.append(str(template).replace("{suppressed}", ", ".join(factors[:3])))

        return self._finalize_reasoning_line(lines, self._tr("report.values.no_conflict_reasoning", "Conflict resolution details are not available."))

    def _build_concordance_reasoning_line(self, row: Dict[str, Any]) -> str:
        lines: list[str] = []
        agreement_level = str(row.get("agreement_level", "")).strip().lower()
        concordance_score = row.get("concordance_score")
        if agreement_level and concordance_score is not None:
            lines.append(f"Agreement level is {agreement_level} ({concordance_score}).")
        elif agreement_level:
            lines.append(f"Agreement level is {agreement_level}.")

        factors = row.get("concordance_factors")
        if isinstance(factors, list):
            snippets = [str(item).strip() for item in factors if str(item).strip()]
            if snippets:
                lines.append("; ".join(snippets[:2]) + ".")

        return self._finalize_reasoning_line(lines, self._tr("report.values.no_concordance_reasoning", "Concordance details are not available."))

    @staticmethod
    def _resolve_activation_code(raw_value: Any) -> str:
        normalized = str(raw_value or "").strip().lower()
        if normalized in {"active_now", "upcoming", "dormant"}:
            return normalized
        if normalized == "high":
            return "active_now"
        if normalized == "medium":
            return "upcoming"
        if normalized == "low":
            return "dormant"
        return ""

    @staticmethod
    def _parse_parashari_narrative(narrative: str, labels: Dict[str, str]) -> Dict[str, str]:
        text = str(narrative or "").strip()
        if not text:
            return {"promise": "", "strength": "", "timing": "", "caution": ""}

        patterns = {
            key: f"{str(label).strip()}:"
            for key, label in labels.items()
            if str(label).strip()
        }
        lowered_text = text.casefold()
        index_map: Dict[str, int] = {}
        for key, marker in patterns.items():
            idx = lowered_text.find(marker.casefold())
            if idx >= 0:
                index_map[key] = idx

        if len(index_map) < 2:
            return {"promise": text, "strength": "", "timing": "", "caution": ""}

        ordered = sorted(index_map.items(), key=lambda item: item[1])
        parsed = {"promise": "", "strength": "", "timing": "", "caution": ""}
        for idx, (key, start_idx) in enumerate(ordered):
            marker = patterns[key]
            content_start = start_idx + len(marker)
            content_end = len(text)
            if idx + 1 < len(ordered):
                content_end = ordered[idx + 1][1]
            parsed[key] = text[content_start:content_end].strip(" .;")
        return parsed

    @staticmethod
    def _strip_labeled_prefix(text: str, label: str) -> str:
        cleaned = str(text or "").strip()
        marker = f"{str(label or '').strip()}:"
        if marker and cleaned.casefold().startswith(marker.casefold()):
            return cleaned[len(marker):].strip()
        return cleaned

    @staticmethod
    def _ensure_terminal_punctuation(text: str) -> str:
        cleaned = str(text or "").strip()
        if not cleaned:
            return cleaned
        if cleaned[-1] in ".!?":
            return cleaned
        return f"{cleaned}."

    def _finalize_reasoning_line(self, lines: list[str], fallback: str) -> str:
        cleaned: list[str] = []
        seen: set[str] = set()
        for line in lines:
            text = self._ensure_terminal_punctuation(str(line).strip())
            if not text:
                continue
            fingerprint = text.casefold()
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            cleaned.append(text)
        if cleaned:
            return " ".join(cleaned)
        return self._ensure_terminal_punctuation(fallback)

    def _build_shadbala_section(self, report_data: Dict[str, Any]) -> list:
        """Builds a compact planetary-strength table from Shadbala output."""
        story = [
            Paragraph(self._tr("report.sections.shadbala", "Shadbala (Six-Fold Strength)"), self.styles["SectionTitle"]),
            Spacer(1, 2 * mm),
        ]

        shadbala_rows = report_data.get("shadbala", {})
        if not isinstance(shadbala_rows, dict) or not shadbala_rows:
            story.append(
                Paragraph(
                    self._tr("report.messages.shadbala_unavailable", "Shadbala data is not available right now."),
                    self.styles["MutedBody"],
                )
            )
            story.append(Spacer(1, 4 * mm))
            return story

        table_data = [[
            self._tr("report.labels.planet", "Planet"),
            self._tr("report.labels.total", "Total"),
            self._tr("report.labels.sthana", "Sthana"),
            self._tr("report.labels.dik", "Dik"),
            self._tr("report.labels.kala", "Kala"),
            self._tr("report.labels.chestha", "Chestha"),
            self._tr("report.labels.naisargika", "Naisargika"),
            self._tr("report.labels.drik", "Drik"),
            self._tr("report.labels.vargottama", "Vargottama"),
        ]]

        rows = []
        for planet, payload in shadbala_rows.items():
            if not isinstance(payload, dict):
                continue
            rows.append(
                (
                    str(payload.get("planet", planet)).title(),
                    self._safe_float(payload.get("total")),
                    self._safe_float(payload.get("sthana_bala")),
                    self._safe_float(payload.get("dik_bala")),
                    self._safe_float(payload.get("kala_bala")),
                    self._safe_float(payload.get("chestha_bala")),
                    self._safe_float(payload.get("naisargika_bala")),
                    self._safe_float(payload.get("drik_bala")),
                    "Yes" if bool(payload.get("is_vargottama")) else "No",
                )
            )

        rows.sort(key=lambda row: row[1], reverse=True)
        for row in rows[:9]:
            table_data.append([
                row[0],
                f"{row[1]:.2f}",
                f"{row[2]:.2f}",
                f"{row[3]:.2f}",
                f"{row[4]:.2f}",
                f"{row[5]:.2f}",
                f"{row[6]:.2f}",
                f"{row[7]:.2f}",
                row[8],
            ])

        table = Table(table_data, colWidths=[24 * mm, 17 * mm, 17 * mm, 15 * mm, 15 * mm, 20 * mm, 24 * mm, 15 * mm, 19 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ede9fe")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#ddd6fe")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ]
            )
        )

        story.extend([table, Spacer(1, 6 * mm)])
        return story

    def _build_transits_section(self, report_data: Dict[str, Any]) -> list:
        """Builds the current Gochar transit summary table."""
        story = [
            Paragraph(self._tr("report.sections.current_transits", "Current Transits (Gochar)"), self.styles["SectionTitle"]),
            Spacer(1, 2 * mm),
        ]

        transit_payload = report_data.get("transits", {})
        transit_rows = {}
        if isinstance(transit_payload, dict):
            transit_rows = transit_payload.get("transits", {})
        if not isinstance(transit_rows, dict) or not transit_rows:
            story.append(
                Paragraph(
                    self._tr("report.messages.transits_unavailable", "Transit data is not available right now."),
                    self.styles["MutedBody"],
                )
            )
            story.append(Spacer(1, 4 * mm))
            return story

        reference = str(transit_payload.get("reference", "moon")).strip().lower() or "moon"
        target_time = str(transit_payload.get("target_time", "")).strip()
        reference_line = (
            f"{self._tr('report.labels.reference', 'Reference')}: {reference.title()}"
            + (f" | {self._tr('report.labels.calculated_at', 'Calculated At')}: {target_time}" if target_time else "")
        )
        story.append(Paragraph(escape(reference_line), self.styles["MutedBody"]))

        table_data = [[
            self._tr("report.labels.planet", "Planet"),
            self._tr("report.labels.sign", "Sign"),
            self._tr("report.labels.house_from_reference", "House From Reference"),
            self._tr("report.labels.retrograde", "Retrograde"),
        ]]

        planet_order = ["sun", "moon", "mars", "mercury", "jupiter", "venus", "saturn", "rahu", "ketu"]
        ordered_names = [name for name in planet_order if name in transit_rows] + [name for name in transit_rows.keys() if name not in planet_order]
        for planet in ordered_names:
            payload = transit_rows.get(planet, {})
            if not isinstance(payload, dict):
                continue
            table_data.append(
                [
                    str(planet).title(),
                    str(payload.get("sign", "")).title(),
                    str(payload.get("house_from_reference", "")),
                    self._tr("report.values.yes", "Yes") if bool(payload.get("is_retrograde")) else self._tr("report.values.no", "No"),
                ]
            )

        table = Table(table_data, colWidths=[30 * mm, 30 * mm, 72 * mm, 30 * mm])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dcfce7")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#14532d")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bbf7d0")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ]
            )
        )
        story.extend([table, Spacer(1, 6 * mm)])
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
            self._tr("report.labels.activation_status", "Activation"),
            self._tr("report.labels.confidence", "Confidence"),
            self._tr("report.labels.source_factors", "Source Factors"),
        ]]
        for row in forecast_rows[:12]:
            event_text = str(row.get("event", "")).strip() or self._tr("report.values.no_event_summary", "No event summary")
            if len(event_text) > 62:
                event_text = event_text[:59].rstrip() + "..."
            source_factors = row.get("source_factors", row.get("dasha_evidence", []))
            source_line = self._format_source_factor_line(source_factors, max_length=68)
            table_data.append(
                [
                    str(row.get("period", "Upcoming")),
                    self._normalize_area(row.get("area", "general")).title(),
                    event_text,
                    self._format_activation_label(row.get("activation_label")),
                    str(self._safe_int(row.get("confidence"))),
                    source_line,
                ]
            )

        table = Table(table_data, colWidths=[20 * mm, 16 * mm, 52 * mm, 20 * mm, 16 * mm, 38 * mm])
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

    def _format_activation_label(self, raw_label: Any) -> str:
        label = str(raw_label or "").strip().lower()
        if label == "active_now":
            return self._tr("report.values.active_now", "Active Now")
        if label == "upcoming":
            return self._tr("report.values.upcoming", "Upcoming")
        if label == "dormant":
            return self._tr("report.values.dormant", "Dormant")
        return self._tr("report.values.unknown", "Unknown")

    def _format_source_factor_line(
        self,
        raw_factors: Any,
        *,
        max_length: int = 90,
        fallback_when_missing: bool = True,
    ) -> str:
        fallback = (
            self._tr("report.values.no_strong_dasha_trigger_yet", "No strong dasha trigger yet.")
            if fallback_when_missing
            else ""
        )
        if not isinstance(raw_factors, (list, tuple)) or not raw_factors:
            return fallback
        cleaned = [str(item).strip() for item in raw_factors if str(item).strip()]
        if not cleaned:
            return fallback
        line = "; ".join(cleaned[:2]).strip()
        if len(line) > max_length:
            return line[: max(0, max_length - 3)].rstrip() + "..."
        return line

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

    @staticmethod
    def _safe_float(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
