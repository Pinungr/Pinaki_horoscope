from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.services.language_manager import LanguageManager
from app.ui.insight_cards import ReasoningSignalRow


class PredictionReasonCard(QFrame):
    """Progressive-disclosure card for one prediction and its backend trace."""

    def __init__(self, language_manager: LanguageManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.language_manager = language_manager
        self.setObjectName("PredictionReasonCard")
        self.setStyleSheet(
            "QFrame#PredictionReasonCard {"
            "background: #ffffff; border: 1px solid #dbe3ef; border-radius: 12px; }"
        )

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.title_label = QLabel("")
        self.title_label.setStyleSheet("font-size: 12px; font-weight: 700; color: #0f172a;")

        self.summary_label = QLabel("")
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet("font-size: 11px; color: #334155; line-height: 1.4;")

        self.signal_row = ReasoningSignalRow()

        explain_row = QHBoxLayout()
        explain_row.setContentsMargins(0, 0, 0, 0)
        explain_row.setSpacing(6)
        self.explain_button = QPushButton("Explain")
        self.explain_button.setCheckable(True)
        self.explain_button.clicked.connect(self._toggle_details)
        self.explain_button.setStyleSheet(
            "QPushButton {"
            "background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; "
            "padding: 3px 8px; font-size: 10px; color: #1e3a8a; font-weight: 600;}"
            "QPushButton:checked {"
            "background: #dbeafe; border: 1px solid #93c5fd;}"
        )
        explain_row.addWidget(self.explain_button)
        explain_row.addStretch(1)

        self.detail_label = QLabel("")
        self.detail_label.setTextFormat(Qt.TextFormat.RichText)
        self.detail_label.setWordWrap(True)
        self.detail_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.detail_label.setStyleSheet(
            "font-size: 10px; color: #334155; background: #f8fafc; border: 1px solid #e2e8f0; "
            "border-radius: 8px; padding: 8px;"
        )
        self.detail_label.setVisible(False)

        layout.addWidget(self.title_label)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.signal_row)
        layout.addLayout(explain_row)
        layout.addWidget(self.detail_label)
        self.setLayout(layout)

    def set_prediction(self, prediction: Mapping[str, Any]) -> None:
        area = str(prediction.get("area", "general")).strip().lower() or "general"
        area_label = "Finance" if area in {"wealth", "financial"} else area.replace("_", " ").title()
        yoga = str(prediction.get("yoga", "")).strip()
        confidence = str(prediction.get("confidence", "")).strip().lower()
        confidence_label = confidence.title() if confidence else "Unknown"
        title_text = f"{area_label} | Confidence {confidence_label}"
        if yoga:
            title_text = f"{title_text} | {yoga}"
        self.title_label.setText(title_text)

        summary = str(
            prediction.get("final_narrative")
            or prediction.get("summary")
            or prediction.get("text")
            or "Narrative is currently unavailable."
        ).strip()
        self.summary_label.setText(summary)

        strength_level = self._resolve_strength_level(prediction)
        activation_level = self._resolve_activation_label(prediction)
        transit_state = self._resolve_transit_state(prediction)
        concordance_level = self._resolve_concordance_level(prediction)
        self.signal_row.set_signals(
            strength_text=f"Strength: {self._strength_display(strength_level)}",
            strength_tone=self._strength_tone(strength_level),
            activation_text=f"Activation: {self._activation_display(activation_level)}",
            activation_tone=self._activation_tone(activation_level),
            transit_text=f"Transit: {self._transit_display(transit_state)}",
            transit_tone=self._transit_tone(transit_state),
            concordance_text=f"Concordance: {self._concordance_display(concordance_level)}",
            concordance_tone=self._concordance_tone(concordance_level),
        )

        detail_html = self._build_detail_html(prediction)
        self.detail_label.setText(detail_html)
        self.explain_button.setChecked(False)
        self._toggle_details(False)

    def apply_translations(self) -> None:
        if self.explain_button.isChecked():
            self.explain_button.setText("Hide")
        else:
            self.explain_button.setText("Explain")

    def _toggle_details(self, checked: bool) -> None:
        self.detail_label.setVisible(bool(checked))
        self.explain_button.setText("Hide" if checked else "Explain")

    def _build_detail_html(self, prediction: Mapping[str, Any]) -> str:
        sections: List[str] = []

        strength_lines = self._collect_strength_lines(prediction)
        dasha_lines = self._collect_dasha_lines(prediction)
        transit_lines = self._collect_transit_lines(prediction)
        varga_lines = self._collect_varga_lines(prediction)
        karaka_lines = self._collect_karaka_lines(prediction)

        sections.append(self._section_html("Strength factors", strength_lines))
        sections.append(self._section_html("Dasha reasoning", dasha_lines))
        sections.append(self._section_html("Transit influence", transit_lines))
        sections.append(self._section_html("Varga alignment", varga_lines))
        sections.append(self._section_html("Karaka contribution", karaka_lines))
        return "<br>".join(section for section in sections if section).strip()

    @staticmethod
    def _section_html(title: str, lines: Iterable[str]) -> str:
        cleaned = [str(line).strip() for line in lines if str(line).strip()]
        if not cleaned:
            cleaned = ["Not available."]
        rendered = "<br>".join(f"- {line}" for line in cleaned[:6])
        return f"<b>{title}</b><br>{rendered}"

    @staticmethod
    def _collect_strength_lines(prediction: Mapping[str, Any]) -> List[str]:
        lines: List[str] = []
        strength = prediction.get("strength")
        if strength:
            lines.append(f"Strength level: {str(strength).strip().lower()}.")
        score = prediction.get("strength_score")
        if score is not None:
            lines.append(f"Strength score: {score}.")

        trace = prediction.get("trace")
        if isinstance(trace, Mapping):
            strength_trace = trace.get("strength")
            if isinstance(strength_trace, Mapping):
                weighted = strength_trace.get("weighted_contribution")
                if weighted is not None:
                    lines.append(f"Weighted strength contribution: {weighted}.")
                input_score = strength_trace.get("input_score")
                if input_score is not None:
                    lines.append(f"Input score after normalization: {input_score}.")

        strength_gate = prediction.get("strength_gate")
        if isinstance(strength_gate, Mapping):
            status = str(strength_gate.get("status", "")).strip().lower()
            if status:
                lines.append(f"Strength gate status: {status}.")
        return lines

    @staticmethod
    def _collect_dasha_lines(prediction: Mapping[str, Any]) -> List[str]:
        lines: List[str] = []
        timing = prediction.get("timing")
        if isinstance(timing, Mapping):
            maha = str(timing.get("mahadasha", "")).strip()
            antar = str(timing.get("antardasha", "")).strip()
            if maha and antar:
                lines.append(f"Dasha window: {maha} Mahadasha with {antar} Antardasha.")
            elif maha:
                lines.append(f"Dasha window: {maha} Mahadasha.")
            activation_level = str(timing.get("activation_level", timing.get("relevance", ""))).strip().lower()
            if activation_level:
                lines.append(f"Activation level: {activation_level}.")
            evidence = timing.get("dasha_evidence")
            if isinstance(evidence, list):
                lines.extend(str(item).strip() for item in evidence if str(item).strip())
        activation_score = prediction.get("activation_score")
        if activation_score is not None:
            lines.append(f"Activation score: {activation_score}.")
        return lines

    @staticmethod
    def _collect_transit_lines(prediction: Mapping[str, Any]) -> List[str]:
        lines: List[str] = []
        transit = prediction.get("transit")
        if isinstance(transit, Mapping):
            support_state = str(transit.get("support_state", "")).strip().lower()
            trigger_level = str(transit.get("trigger_level", "")).strip().lower()
            if support_state:
                lines.append(f"Transit support state: {support_state}.")
            if trigger_level:
                lines.append(f"Transit trigger level: {trigger_level}.")
            source_factors = transit.get("source_factors")
            if isinstance(source_factors, list):
                lines.extend(str(item).strip() for item in source_factors if str(item).strip())
        return lines

    @staticmethod
    def _collect_varga_lines(prediction: Mapping[str, Any]) -> List[str]:
        lines: List[str] = []
        agreement = str(prediction.get("agreement_level", "")).strip().lower()
        if agreement:
            lines.append(f"Agreement level: {agreement}.")
        concordance_score = prediction.get("concordance_score")
        if concordance_score is not None:
            lines.append(f"Concordance score: {concordance_score}.")
        factors = prediction.get("concordance_factors")
        if isinstance(factors, list):
            lines.extend(str(item).strip() for item in factors if str(item).strip())
        return lines

    @staticmethod
    def _collect_karaka_lines(prediction: Mapping[str, Any]) -> List[str]:
        lines: List[str] = []
        karaka_source = str(prediction.get("karaka_source", "")).strip().lower()
        if karaka_source:
            lines.append(f"Karaka source: {karaka_source}.")
        impact = prediction.get("karaka_impact")
        if isinstance(impact, list):
            lines.extend(str(item).strip() for item in impact if str(item).strip())
        return lines

    @staticmethod
    def _resolve_strength_level(prediction: Mapping[str, Any]) -> str:
        strength = str(prediction.get("strength", "")).strip().lower()
        if strength in {"strong", "medium", "weak"}:
            return strength
        strength_gate = prediction.get("strength_gate")
        if isinstance(strength_gate, Mapping):
            level = str(strength_gate.get("chart_strength_level", "")).strip().lower()
            if level in {"strong", "medium", "weak"}:
                return level
        return "unknown"

    @staticmethod
    def _resolve_activation_label(prediction: Mapping[str, Any]) -> str:
        activation = str(prediction.get("activation_label", "")).strip().lower()
        if activation in {"active_now", "upcoming", "dormant"}:
            return activation
        timing = prediction.get("timing")
        if isinstance(timing, Mapping):
            level = str(timing.get("activation_level", timing.get("relevance", ""))).strip().lower()
            if level == "high":
                return "active_now"
            if level == "medium":
                return "upcoming"
            if level == "low":
                return "dormant"
        return "unknown"

    @staticmethod
    def _resolve_transit_state(prediction: Mapping[str, Any]) -> str:
        transit = prediction.get("transit")
        if isinstance(transit, Mapping):
            support_state = str(transit.get("support_state", "")).strip().lower()
            if support_state in {"amplifying", "neutral", "suppressing"}:
                return support_state
        return "unknown"

    @staticmethod
    def _resolve_concordance_level(prediction: Mapping[str, Any]) -> str:
        level = str(prediction.get("agreement_level", "")).strip().lower()
        if level in {"high", "medium", "low"}:
            return level
        return "unknown"

    @staticmethod
    def _strength_display(level: str) -> str:
        return {"strong": "Strong", "medium": "Moderate", "weak": "Weak"}.get(level, "Unknown")

    @staticmethod
    def _strength_tone(level: str) -> str:
        return {"strong": "strong", "medium": "moderate", "weak": "weak"}.get(level, "unknown")

    @staticmethod
    def _activation_display(level: str) -> str:
        return {
            "active_now": "Active Now",
            "upcoming": "Upcoming",
            "dormant": "Dormant",
        }.get(level, "Unknown")

    @staticmethod
    def _activation_tone(level: str) -> str:
        return {"active_now": "active", "upcoming": "upcoming", "dormant": "dormant"}.get(level, "unknown")

    @staticmethod
    def _transit_display(level: str) -> str:
        return {
            "amplifying": "Amplifying",
            "neutral": "Neutral",
            "suppressing": "Suppressing",
        }.get(level, "Unknown")

    @staticmethod
    def _transit_tone(level: str) -> str:
        return {"amplifying": "amplifying", "neutral": "neutral", "suppressing": "suppressing"}.get(level, "unknown")

    @staticmethod
    def _concordance_display(level: str) -> str:
        return {"high": "High", "medium": "Medium", "low": "Low"}.get(level, "Unknown")

    @staticmethod
    def _concordance_tone(level: str) -> str:
        return {"high": "high", "medium": "medium", "low": "low"}.get(level, "unknown")


class PredictionPanel(QWidget):
    """Scrollable container that keeps prediction reasoning readable and compact."""

    def __init__(self, language_manager: LanguageManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.language_manager = language_manager
        self._all_predictions: List[Dict[str, Any]] = []
        self._active_area_filter = "all"
        self._cards: List[PredictionReasonCard] = []

        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        self.title_label = QLabel("Prediction Reasoning")
        self.title_label.setStyleSheet("font-size: 12px; font-weight: 700; color: #0f172a;")

        self.empty_label = QLabel("Generate or load a chart to inspect detailed reasoning.")
        self.empty_label.setProperty("role", "empty-state")
        self.empty_label.setWordWrap(True)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_container = QWidget()
        self.cards_layout = QVBoxLayout()
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(8)
        self.cards_layout.addStretch(1)
        self.scroll_container.setLayout(self.cards_layout)
        self.scroll.setWidget(self.scroll_container)

        root.addWidget(self.title_label)
        root.addWidget(self.empty_label)
        root.addWidget(self.scroll)
        self.setLayout(root)
        self._refresh_visibility()

    def apply_translations(self) -> None:
        self.title_label.setText("Prediction Reasoning")
        if not self._all_predictions:
            self.empty_label.setText("Generate or load a chart to inspect detailed reasoning.")
        for card in self._cards:
            card.apply_translations()

    def set_area_filter(self, area: str) -> None:
        normalized = str(area or "all").strip().lower() or "all"
        if normalized not in {"all", "career", "marriage", "finance"}:
            normalized = "all"
        self._active_area_filter = normalized
        self._render_cards()

    def set_predictions(self, predictions: Any) -> None:
        rows: List[Dict[str, Any]] = []
        if isinstance(predictions, list):
            rows = [dict(row) for row in predictions if isinstance(row, Mapping)]
        elif isinstance(predictions, Mapping):
            rows = [dict(predictions)]
        self._all_predictions = rows
        self._render_cards()

    def clear(self) -> None:
        self._all_predictions = []
        self._render_cards()

    def _render_cards(self) -> None:
        for card in self._cards:
            self.cards_layout.removeWidget(card)
            card.deleteLater()
        self._cards = []

        visible_rows = [row for row in self._all_predictions if self._matches_filter(row)]
        if not visible_rows:
            self._refresh_visibility()
            return

        for row in visible_rows[:6]:
            card = PredictionReasonCard(self.language_manager)
            card.set_prediction(row)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)
            self._cards.append(card)

        self._refresh_visibility()

    def _matches_filter(self, row: Mapping[str, Any]) -> bool:
        if self._active_area_filter == "all":
            return True
        area = str(row.get("area", "general")).strip().lower() or "general"
        normalized = "finance" if area in {"wealth", "financial"} else area
        return normalized == self._active_area_filter

    def _refresh_visibility(self) -> None:
        has_cards = bool(self._cards)
        self.empty_label.setVisible(not has_cards)
        self.scroll.setVisible(has_cards)
