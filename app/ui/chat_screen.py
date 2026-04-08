from __future__ import annotations

from typing import Any, Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from app.ui.theme import SPACE_8, SPACE_12, SPACE_16, SPACE_24, set_button_variant
from app.ui.theme import fade_in_widget, set_button_icon


class ChatScreen(QWidget):
    """
    Reusable horoscope chat UI.

    By default, the widget emits `chat_requested(user_id, query)` so a controller
    can handle business logic externally. If a chat service is configured, the
    widget can also execute the chat flow directly.
    """

    chat_requested = pyqtSignal(int, str)

    def __init__(self, chat_service: Optional[Any] = None):
        super().__init__()
        self.chat_service = chat_service
        self.active_user_id: Optional[int] = None
        self._last_chat_result: Optional[dict] = None
        self._busy = False
        self._suggestions = [
            "When will I get promotion?",
            "How is my marriage life?",
            "Financial growth timing?",
        ]
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(SPACE_24, SPACE_24, SPACE_24, SPACE_24)
        layout.setSpacing(SPACE_16)
        header_row = QHBoxLayout()
        header_row.setSpacing(SPACE_12)

        self.title_label = QLabel("AI Horoscope Chat")
        self.title_label.setProperty("role", "title")
        self.mode_badge = QLabel("Local Mode")
        self.mode_badge.setStyleSheet(
            "background-color: #e2e8f0; color: #334155; "
            "border-radius: 10px; padding: 4px 10px; font-size: 11px; font-weight: bold;"
        )

        self.subtitle_label = QLabel(
            "Ask questions like: When will I get a job? Is marriage good for me?"
        )
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setProperty("role", "subtitle")
        self.status_label = QLabel("Ready for your next question.")
        self.status_label.setProperty("role", "subtitle")
        self.status_label.setWordWrap(True)

        header_row.addWidget(self.title_label)
        header_row.addStretch()
        header_row.addWidget(self.mode_badge)

        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setPlaceholderText("Your horoscope conversation will appear here...")
        self.chat_history.setStyleSheet(
            "background: #ffffff; border: 1px solid #dbe3ef; border-radius: 12px; padding: 8px;"
        )
        self.empty_state_label = QLabel("No conversation yet. Ask a timing question to begin.")
        self.empty_state_label.setProperty("role", "empty-state")
        self.empty_state_label.setWordWrap(True)

        suggestion_row = QHBoxLayout()
        suggestion_row.setSpacing(SPACE_8)
        self.suggestion_buttons: list[QPushButton] = []
        for suggestion in self._suggestions:
            button = QPushButton(suggestion)
            button.setProperty("chip", "true")
            button.clicked.connect(lambda checked=False, text=suggestion: self._handle_suggestion(text))
            suggestion_row.addWidget(button)
            self.suggestion_buttons.append(button)
        suggestion_row.addStretch(1)

        input_row = QHBoxLayout()
        self.input_box = QTextEdit()
        self.input_box.setPlaceholderText("Type your horoscope question here...")
        self.input_box.setMaximumHeight(80)

        self.send_button = QPushButton("Send")
        self.send_button.setMinimumWidth(96)
        self.send_button.clicked.connect(self.handle_send)
        set_button_variant(self.send_button, "primary")
        set_button_icon(self.send_button, "send")

        self.why_button = QPushButton("Why?")
        self.why_button.setMinimumWidth(86)
        self.why_button.setEnabled(False)
        self.why_button.clicked.connect(self._show_reasoning_popup)
        set_button_variant(self.why_button, "ghost")
        set_button_icon(self.why_button, "why")

        input_row.addWidget(self.input_box, 1)
        input_row.addWidget(self.why_button)
        input_row.addWidget(self.send_button)

        layout.addLayout(header_row)
        layout.addWidget(self.subtitle_label)
        layout.addWidget(self.status_label)
        layout.addLayout(suggestion_row)
        layout.addWidget(self.empty_state_label)
        layout.addWidget(self.chat_history, 1)
        layout.addLayout(input_row)

        self.setLayout(layout)

    def set_active_user(self, user_id: Optional[int]) -> None:
        """Sets the currently selected/generated user for chat queries."""
        self.active_user_id = user_id

    def configure_chat_service(self, chat_service: Any) -> None:
        """Injects a chat service after widget construction."""
        self.chat_service = chat_service

    def set_mode_badge(self, mode: str) -> None:
        """Updates the visible chat mode badge."""
        normalized = str(mode or "local").strip().lower()
        styles = {
            "local": ("Local Mode", "#e2e8f0", "#334155"),
            "openai": ("OpenAI Mode", "#dcfce7", "#166534"),
            "fallback": ("OpenAI Fallback", "#fef3c7", "#92400e"),
        }
        label, bg_color, text_color = styles.get(normalized, styles["local"])
        self.mode_badge.setText(label)
        self.mode_badge.setStyleSheet(
            f"background-color: {bg_color}; color: {text_color}; "
            "border-radius: 10px; padding: 4px 10px; font-size: 11px; font-weight: bold;"
        )

    def clear_chat(self) -> None:
        """Clears the visible chat history."""
        self.chat_history.clear()
        self.empty_state_label.setVisible(True)
        fade_in_widget(self.empty_state_label)

    def append_user_message(self, text: str) -> None:
        """Appends a styled user message to the chat history."""
        self.empty_state_label.setVisible(False)
        message = self._format_message("You", text, "#1d4ed8")
        self.chat_history.append(message)

    def append_assistant_message(self, text: str) -> None:
        """Appends a styled assistant message to the chat history."""
        self.empty_state_label.setVisible(False)
        message = self._format_message("Horoscope AI", text, "#7c3aed")
        self.chat_history.append(message)

    def append_system_message(self, text: str) -> None:
        """Appends a neutral system message to the chat history."""
        self.empty_state_label.setVisible(False)
        message = self._format_message("System", text, "#475569")
        self.chat_history.append(message)

    def handle_send(self) -> None:
        """Validates input and either emits a request or calls the injected service."""
        query = self.input_box.toPlainText().strip()
        if not query:
            QMessageBox.warning(self, "Validation", "Please enter a question before sending.")
            return

        if self.active_user_id is None:
            QMessageBox.warning(self, "No User", "Please generate or load a user chart first.")
            return

        self.append_user_message(query)
        self.input_box.clear()

        if self.chat_service is not None:
            self.set_busy(True, "Analyzing your chart context...")
            try:
                result = self.chat_service.ask(self.active_user_id, query)
                self.display_chat_result(result)
            except Exception as exc:
                self.append_system_message(f"Chat request failed: {exc}")
                self.set_status("Chat request failed. Please retry.", level="error")
            finally:
                self.set_busy(False)
            return

        self.chat_requested.emit(self.active_user_id, query)

    def display_chat_response(self, response: str) -> None:
        """Displays a completed assistant response."""
        self.append_assistant_message(response)

    def display_chat_result(self, result: dict) -> None:
        """Displays the response from a structured chat-service result."""
        self._last_chat_result = dict(result or {})
        source = str(result.get("response_source", "local")).strip().lower()
        if source == "openai":
            self.set_mode_badge("openai")
            self.append_system_message("Response generated with OpenAI refinement.")
        elif result.get("ai_error"):
            self.set_mode_badge("fallback")
            self.append_system_message("OpenAI refinement was unavailable, so local chat was used.")
        else:
            self.set_mode_badge("local")
        self.why_button.setEnabled(bool(self._extract_reasoning_lines(self._last_chat_result)))
        self.append_assistant_message(result.get("response", "No response generated."))
        self.set_status("Response ready.", level="success")

    def _handle_suggestion(self, suggestion: str) -> None:
        self.input_box.setPlainText(str(suggestion or "").strip())
        if self.active_user_id is not None:
            self.handle_send()

    def _extract_reasoning_lines(self, result: Optional[dict]) -> list[str]:
        if not isinstance(result, dict):
            return []
        lines: list[str] = []

        event_prediction = result.get("event_prediction", {})
        if isinstance(event_prediction, dict):
            answer = str(event_prediction.get("answer", "")).strip()
            if answer:
                lines.append(answer)
            reasoning_rows = event_prediction.get("reasoning", [])
            if isinstance(reasoning_rows, list):
                for row in reasoning_rows:
                    if not isinstance(row, dict):
                        continue
                    explanation = str(row.get("explanation", "")).strip()
                    if explanation:
                        lines.append(f"- {explanation}")
                    factors = row.get("supporting_factors", [])
                    if isinstance(factors, list):
                        for factor in factors[:4]:
                            if str(factor).strip():
                                lines.append(f"  - {str(factor).strip()}")

        if lines:
            return lines

        data = result.get("data", {})
        if not isinstance(data, dict):
            return lines
        reasoning_rows = data.get("reasoning", [])
        if isinstance(reasoning_rows, list):
            for row in reasoning_rows:
                if not isinstance(row, dict):
                    continue
                explanation = str(row.get("explanation", "")).strip()
                if explanation:
                    lines.append(f"- {explanation}")
                factors = row.get("supporting_factors", [])
                if isinstance(factors, list):
                    for factor in factors[:4]:
                        if str(factor).strip():
                            lines.append(f"  - {str(factor).strip()}")
        return lines

    def _show_reasoning_popup(self) -> None:
        reasoning_lines = self._extract_reasoning_lines(self._last_chat_result)
        if not reasoning_lines:
            QMessageBox.information(self, "Why?", "No detailed reasoning is available for the latest response.")
            return
        QMessageBox.information(self, "Why?", "\n".join(reasoning_lines))

    def set_status(self, message: str, level: str = "info") -> None:
        """Updates inline chat status feedback for loading/success/error moments."""
        text = str(message or "").strip() or "Ready for your next question."
        normalized = str(level or "info").strip().lower()
        palettes = {
            "info": ("#475569", "transparent", "transparent"),
            "success": ("#166534", "#f0fdf4", "#86efac"),
            "warning": ("#92400e", "#fffbeb", "#fcd34d"),
            "error": ("#991b1b", "#fef2f2", "#fca5a5"),
        }
        color, background, border = palettes.get(normalized, palettes["info"])
        self.status_label.setText(text)
        self.status_label.setStyleSheet(
            f"font-size: 12px; color: {color}; background: {background}; border: 1px solid {border}; "
            "border-radius: 10px; padding: 4px 8px;"
        )
        fade_in_widget(self.status_label)

    def set_busy(self, busy: bool, message: str = "Analyzing...") -> None:
        """Locks chat controls temporarily while inference is running."""
        self._busy = bool(busy)
        self.send_button.setEnabled(not self._busy)
        self.input_box.setEnabled(not self._busy)
        for button in self.suggestion_buttons:
            button.setEnabled(not self._busy)
        self.why_button.setEnabled((not self._busy) and bool(self._extract_reasoning_lines(self._last_chat_result)))

        if self._busy:
            self.send_button.setText("Sending...")
            self.set_status(message, level="info")
            QApplication.processEvents()
            return

        self.send_button.setText("Send")
        if self.status_label.text().strip().lower().startswith("analyzing"):
            self.set_status("Ready for your next question.", level="info")

    @staticmethod
    def _format_message(speaker: str, text: str, color: str) -> str:
        safe_text = str(text or "").replace("\n", "<br>")
        return (
            f"<div style='margin-bottom: 10px;'>"
            f"<span style='font-weight: bold; color: {color};'>{speaker}:</span> "
            f"<span>{safe_text}</span>"
            f"</div>"
        )
