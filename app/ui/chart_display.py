from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from typing import List, Dict, Any, Optional
import re
from app.services.language_manager import LanguageManager
from app.ui.theme import (
    SPACE_8,
    SPACE_12,
    SPACE_16,
    SPACE_24,
    fade_in_widget,
    set_button_icon,
    set_button_variant,
)
from core.predictions.aggregation_service import aggregate_predictions
from core.predictions.prediction_service import get_prediction

class ChartDisplay(QWidget):
    generate_report_requested = pyqtSignal()
    area_filter_changed = pyqtSignal(str)

    def __init__(self, language_manager: LanguageManager | None = None):
        super().__init__()
        self.language_manager = language_manager or LanguageManager()
        self._report_busy = False
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(SPACE_24, SPACE_24, SPACE_24, SPACE_24)
        layout.setSpacing(SPACE_16)

        self.title_label = QLabel()
        self.title_label.setProperty("role", "title")
        self.subtitle_label = QLabel("Explore your core strengths, timing, and practical predictions.")
        self.subtitle_label.setProperty("role", "subtitle")
        self.subtitle_label.setWordWrap(True)
        
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
        self._latest_localized_predictions: Any = None
        self._prediction_display_state = "awaiting"
        self._active_area_filter = "all"
        self._cache_debug_enabled = False
        
        self.predictions_label = QLabel()
        self.predictions_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 10px;")
        self.cache_debug_badge = QLabel("")
        self.cache_debug_badge.setVisible(False)
        self.cache_debug_badge.setStyleSheet(
            "font-size: 10px; color: #334155; background: #f8fafc; border: 1px solid #cbd5e1; "
            "border-radius: 8px; padding: 2px 8px;"
        )
        self.status_badge = QLabel("")
        self.status_badge.setVisible(False)
        self.status_badge.setStyleSheet(
            "font-size: 11px; color: #1e3a8a; background: #eff6ff; border: 1px solid #bfdbfe; "
            "border-radius: 10px; padding: 4px 10px;"
        )

        self.top_insights_label = QLabel("Top Insights")
        self.top_insights_label.setStyleSheet("font-size: 13px; font-weight: bold; margin-top: 4px;")

        self.confidence_label = QLabel("Overall Confidence")
        self.confidence_label.setStyleSheet("font-size: 12px; font-weight: bold; margin-top: 4px;")
        self.confidence_value_label = QLabel("0%")
        self.confidence_value_label.setStyleSheet("font-size: 11px; color: #475569;")
        confidence_row = QHBoxLayout()
        confidence_row.setSpacing(8)
        self.confidence_bar = QProgressBar()
        self.confidence_bar.setMinimum(0)
        self.confidence_bar.setMaximum(100)
        self.confidence_bar.setValue(0)
        self.confidence_bar.setTextVisible(False)
        self.confidence_bar.setFixedHeight(10)
        self._set_confidence_visual(0)
        confidence_row.addWidget(self.confidence_bar, 1)
        confidence_row.addWidget(self.confidence_value_label)

        self._insight_cards: Dict[str, Dict[str, QLabel]] = {}
        insights_row = QHBoxLayout()
        insights_row.setSpacing(SPACE_8)
        for area, title in (("career", "Career"), ("marriage", "Marriage"), ("finance", "Finance")):
            card = QFrame()
            card.setProperty("role", "insight-card")
            card_layout = QVBoxLayout()
            card_layout.setContentsMargins(8, 6, 8, 6)
            card_layout.setSpacing(2)
            title_label = QLabel(title)
            title_label.setStyleSheet("font-size: 11px; font-weight: bold; color: #334155;")
            value_label = QLabel("No major signal yet")
            value_label.setWordWrap(True)
            value_label.setStyleSheet("font-size: 11px; color: #475569;")
            card_layout.addWidget(title_label)
            card_layout.addWidget(value_label)
            card.setLayout(card_layout)
            insights_row.addWidget(card, 1)
            self._insight_cards[area] = {"title": title_label, "value": value_label}

        self.chart_insight_label = QLabel()
        self.chart_insight_label.setWordWrap(True)
        self.chart_insight_label.setStyleSheet(
            "background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; "
            "padding: 10px 12px; color: #334155; font-size: 12px; line-height: 1.45;"
        )

        filter_row = QHBoxLayout()
        filter_row.setSpacing(SPACE_8)
        self._area_filter_buttons: Dict[str, QPushButton] = {}
        for area, label in (("all", "All"), ("career", "Career"), ("marriage", "Marriage"), ("finance", "Finance")):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setProperty("chip", "true")
            button.clicked.connect(lambda checked=False, value=area: self._set_area_filter(value))
            filter_row.addWidget(button)
            self._area_filter_buttons[area] = button
        filter_row.addStretch(1)
        
        self.predictions_text = QLabel()
        self.predictions_text.setWordWrap(True)
        self.predictions_text.setStyleSheet(
            "background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; "
            "padding: 10px 12px; color: #1e293b; line-height: 1.5;"
        )

        self.report_button = QPushButton()
        self.report_button.setEnabled(False)
        self.report_button.clicked.connect(self.generate_report_requested.emit)
        set_button_variant(self.report_button, "primary")
        set_button_icon(self.report_button, "report")

        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)
        layout.addWidget(self.status_badge)
        layout.addWidget(self.cache_debug_badge)
        layout.addWidget(self.kundli_widget)
        layout.addWidget(self.chart_insight_label)
        layout.addWidget(self.predictions_label)
        layout.addWidget(self.top_insights_label)
        layout.addLayout(insights_row)
        layout.addWidget(self.confidence_label)
        layout.addLayout(confidence_row)
        layout.addLayout(filter_row)
        layout.addWidget(self.predictions_text)
        layout.addWidget(self.report_button)
        
        self.setLayout(layout)
        self._set_area_filter("all", emit_signal=False)
        self.apply_translations()

    def _tr(self, key: str) -> str:
        return self.language_manager.get_text(key)

    def apply_translations(self) -> None:
        self.title_label.setText(self._tr("ui.chart_information"))
        self.predictions_label.setText(f"{self._tr('ui.predictions')}:")
        self.top_insights_label.setText("Top Insights")
        self.confidence_label.setText("Overall Confidence")
        self._clear_chart_insight()
        if self._prediction_display_state == "awaiting":
            self.predictions_text.setText(self._tr("ui.awaiting_generation"))
        elif self._prediction_display_state == "empty":
            self.predictions_text.setText(self._tr("ui.no_predictions_found"))
            self.display_top_insights({})
        self.report_button.setText("Generating PDF..." if self._report_busy else self._tr("ui.generate_report"))
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
        self._refresh_cache_debug_visibility()

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
        self.report_button.setEnabled(bool(chart_data) and not self._report_busy)

    def display_predictions(self, predictions: Any):
        """Show structured scored predictions without breaking older list-based payloads."""
        if not predictions:
            self.kundli_widget.clear_insights()
            self._latest_localized_predictions = None
            self._prediction_display_state = "empty"
            self.predictions_text.setText(self._tr("ui.no_predictions_found"))
            self.display_top_insights({})
            self._set_confidence_visual(0)
            return

        localized_predictions = self._localize_predictions(predictions)
        self._latest_localized_predictions = localized_predictions
        self._prediction_display_state = "content"

        if isinstance(localized_predictions, dict):
            self._set_confidence_visual(self._derive_confidence_from_predictions(localized_predictions))
        self._render_predictions(localized_predictions)
        self.kundli_widget.set_insights(**self._build_chart_insights(localized_predictions))

    def _render_predictions(self, localized_predictions: Any) -> None:
        html = "<ul>"
        rows_rendered = 0
        if isinstance(localized_predictions, dict):
            sorted_categories = sorted(
                [
                    (str(category).strip().lower(), float((details or {}).get("score", 0.0) or 0.0))
                    for category, details in localized_predictions.items()
                    if str(category or "").strip().lower() != "system"
                ],
                key=lambda item: item[1],
                reverse=True,
            )
            top_areas = [category for category, _ in sorted_categories[:3]]
            self.display_top_insights({"top_areas": top_areas})
            for category, details in localized_predictions.items():
                normalized_area = self._normalize_area_name(category)
                if self._active_area_filter != "all" and normalized_area != self._active_area_filter:
                    continue

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
                rows_rendered += 1
        else:
            self.display_top_insights({})
            for p in localized_predictions:
                normalized_area = self._normalize_area_name(p.get("category") or p.get("area") or "general")
                if self._active_area_filter != "all" and normalized_area != self._active_area_filter:
                    continue

                score_value = float(p.get("score", 0) or 0)
                score_color = "#d9534f" if score_value > 50 else "#5bc0de" if score_value > 20 else "#777"
                category_text = str(p.get("category", "general")).upper()
                prediction_text = str(p.get("text", "")).strip()
                html += f"<li style='margin-bottom: 5px;'>"
                html += f"<span style='color: white; background-color: {score_color}; border-radius: 3px; padding: 2px 4px; font-size: 10px; margin-right: 5px;'>"
                html += f"{category_text} | {score_value:.0f}</span> "
                html += f"{prediction_text}</li>"
                rows_rendered += 1
        html += "</ul>"

        if rows_rendered == 0 and self._active_area_filter != "all":
            self.predictions_text.setText(f"No {self._active_area_filter.title()} predictions available yet.")
            return
        self.predictions_text.setText(html)

    def display_top_insights(self, summary: Dict[str, Any] | None) -> None:
        """Updates the top insight cards from unified summary.top_areas data."""
        top_areas_raw = []
        time_focus_raw = []
        if isinstance(summary, dict):
            raw = summary.get("top_areas", [])
            if isinstance(raw, list):
                top_areas_raw = [self._normalize_area_name(item) for item in raw if str(item or "").strip()]
            time_focus = summary.get("time_focus", [])
            if isinstance(time_focus, list):
                time_focus_raw = [self._normalize_area_name(item) for item in time_focus if str(item or "").strip()]
            confidence_score = summary.get("confidence_score")
            if confidence_score is not None:
                self._set_confidence_visual(confidence_score)
        rank_by_area = {area: index + 1 for index, area in enumerate(top_areas_raw)}
        time_focus_set = set(time_focus_raw)

        for area, labels in self._insight_cards.items():
            if area in rank_by_area:
                labels["value"].setText(f"Top focus #{rank_by_area[area]}")
                labels["value"].setStyleSheet("font-size: 11px; color: #166534; font-weight: bold;")
            elif area in time_focus_set:
                labels["value"].setText("Timing active")
                labels["value"].setStyleSheet("font-size: 11px; color: #92400e; font-weight: bold;")
            else:
                labels["value"].setText("No major signal yet")
                labels["value"].setStyleSheet("font-size: 11px; color: #475569;")

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
                detail_items = self._localized_detail_items(details_copy)
                if detail_items:
                    details_copy["details"] = detail_items
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
        positive_aggregation = aggregate_predictions(
            details.get("positive_summary_keys", []),
            self.language_manager.current_language,
        )
        negative_aggregation = aggregate_predictions(
            details.get("negative_summary_keys", []),
            self.language_manager.current_language,
        )
        positive_text = positive_aggregation.get("summary", "")
        negative_text = negative_aggregation.get("summary", "")
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

    def _localized_detail_items(self, details: Dict[str, Any]) -> List[Dict[str, str]]:
        positive_details = aggregate_predictions(
            details.get("positive_summary_keys", []),
            self.language_manager.current_language,
        ).get("details", [])
        negative_details = aggregate_predictions(
            details.get("negative_summary_keys", []),
            self.language_manager.current_language,
        ).get("details", [])
        return list(positive_details) + list(negative_details)

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

    def _set_area_filter(self, area: str, emit_signal: bool = True) -> None:
        normalized = self._normalize_area_name(area)
        if normalized not in {"all", "career", "marriage", "finance"}:
            normalized = "all"
        self._active_area_filter = normalized

        for key, button in self._area_filter_buttons.items():
            button.setChecked(key == normalized)

        if self._latest_localized_predictions is not None:
            self._render_predictions(self._latest_localized_predictions)

        if emit_signal:
            self.area_filter_changed.emit(normalized)

    def _set_confidence_visual(self, score_value: Any) -> None:
        score = 0
        try:
            score = int(round(float(score_value)))
        except (TypeError, ValueError):
            score = 0
        score = max(0, min(100, score))

        if score >= 80:
            bar_color = "#16a34a"
        elif score >= 50:
            bar_color = "#d97706"
        else:
            bar_color = "#dc2626"

        self.confidence_bar.setValue(score)
        self.confidence_bar.setStyleSheet(
            "QProgressBar { background: #e2e8f0; border: 1px solid #cbd5e1; border-radius: 6px; }"
            f"QProgressBar::chunk {{ background-color: {bar_color}; border-radius: 6px; }}"
        )
        self.confidence_value_label.setText(f"{score}%")
        self.confidence_value_label.setStyleSheet(f"font-size: 11px; color: {bar_color}; font-weight: bold;")

    def _derive_confidence_from_predictions(self, predictions: Dict[str, Any]) -> int:
        mapped_scores: List[int] = []
        for category, details in predictions.items():
            if self._normalize_area_name(category) == "general":
                continue
            if not isinstance(details, dict):
                continue

            confidence = str(details.get("confidence", "")).strip().lower()
            if confidence == "high":
                mapped_scores.append(86)
            elif confidence == "medium":
                mapped_scores.append(66)
            elif confidence == "low":
                mapped_scores.append(42)
            else:
                raw_score = float(details.get("score", 0.0) or 0.0)
                if raw_score >= 2:
                    mapped_scores.append(84)
                elif raw_score >= 1:
                    mapped_scores.append(64)
                elif raw_score < 0:
                    mapped_scores.append(34)
                else:
                    mapped_scores.append(50)

        if not mapped_scores:
            return 0
        return int(round(sum(mapped_scores) / len(mapped_scores)))

    def _normalize_area_name(self, area: Any) -> str:
        normalized = str(area or "").strip().lower() or "general"
        if normalized in {"financial", "wealth"}:
            return "finance"
        if normalized in {"all", "career", "marriage", "finance"}:
            return normalized
        return normalized

    def set_cache_debug_mode(self, enabled: bool) -> None:
        """Toggles cache-debug badge visibility without affecting normal UI."""
        self._cache_debug_enabled = bool(enabled)
        self._refresh_cache_debug_visibility()

    def set_cache_debug_status(self, label: str, hit_state: bool | None = None) -> None:
        """
        Updates the debug badge with cache state details.

        hit_state:
        - True => all hit (green)
        - False => all miss (red)
        - None => mixed/neutral (amber)
        """
        text = str(label or "").strip()
        if not text:
            self.cache_debug_badge.setText("")
            self._refresh_cache_debug_visibility()
            return

        if hit_state is True:
            color = "#166534"
            border = "#86efac"
            bg = "#f0fdf4"
        elif hit_state is False:
            color = "#b91c1c"
            border = "#fca5a5"
            bg = "#fef2f2"
        else:
            color = "#92400e"
            border = "#fcd34d"
            bg = "#fffbeb"

        self.cache_debug_badge.setText(f"Cache: {text}")
        self.cache_debug_badge.setStyleSheet(
            f"font-size: 10px; color: {color}; background: {bg}; border: 1px solid {border}; "
            "border-radius: 8px; padding: 2px 8px;"
        )
        self._refresh_cache_debug_visibility()

    def _refresh_cache_debug_visibility(self) -> None:
        should_show = self._cache_debug_enabled and bool(self.cache_debug_badge.text().strip())
        self.cache_debug_badge.setVisible(should_show)

    def set_status(self, message: str, level: str = "info") -> None:
        """Shows a compact status badge for loading/success/error feedback."""
        text = str(message or "").strip()
        if not text:
            self.status_badge.setVisible(False)
            self.status_badge.setText("")
            return

        normalized = str(level or "info").strip().lower()
        palettes = {
            "info": ("#1e3a8a", "#eff6ff", "#bfdbfe"),
            "success": ("#166534", "#f0fdf4", "#86efac"),
            "warning": ("#92400e", "#fffbeb", "#fcd34d"),
            "error": ("#991b1b", "#fef2f2", "#fca5a5"),
        }
        color, background, border = palettes.get(normalized, palettes["info"])
        self.status_badge.setText(text)
        self.status_badge.setStyleSheet(
            f"font-size: 11px; color: {color}; background: {background}; border: 1px solid {border}; "
            "border-radius: 10px; padding: 4px 10px;"
        )
        self.status_badge.setVisible(True)
        fade_in_widget(self.status_badge)

    def set_report_busy(self, busy: bool) -> None:
        """Adds visible feedback while PDF generation is in progress."""
        self._report_busy = bool(busy)
        if self._report_busy:
            self.report_button.setText("Generating PDF...")
            self.report_button.setEnabled(False)
            return
        self.report_button.setText(self._tr("ui.generate_report"))
        self.report_button.setEnabled(bool(self._latest_chart_data))
