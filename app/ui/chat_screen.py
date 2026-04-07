from __future__ import annotations

from typing import Any, Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


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
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout()
        header_row = QHBoxLayout()

        self.title_label = QLabel("AI Horoscope Chat")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.mode_badge = QLabel("Local Mode")
        self.mode_badge.setStyleSheet(
            "background-color: #e2e8f0; color: #334155; "
            "border-radius: 10px; padding: 4px 10px; font-size: 11px; font-weight: bold;"
        )

        self.subtitle_label = QLabel(
            "Ask questions like: When will I get a job? Is marriage good for me?"
        )
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setStyleSheet("color: #556070; margin-bottom: 6px;")

        header_row.addWidget(self.title_label)
        header_row.addStretch()
        header_row.addWidget(self.mode_badge)

        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setPlaceholderText("Your horoscope conversation will appear here...")

        input_row = QHBoxLayout()
        self.input_box = QTextEdit()
        self.input_box.setPlaceholderText("Type your horoscope question here...")
        self.input_box.setMaximumHeight(80)

        self.send_button = QPushButton("Send")
        self.send_button.setMinimumWidth(96)
        self.send_button.clicked.connect(self.handle_send)

        input_row.addWidget(self.input_box, 1)
        input_row.addWidget(self.send_button)

        layout.addLayout(header_row)
        layout.addWidget(self.subtitle_label)
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

    def append_user_message(self, text: str) -> None:
        """Appends a styled user message to the chat history."""
        message = self._format_message("You", text, "#1d4ed8")
        self.chat_history.append(message)

    def append_assistant_message(self, text: str) -> None:
        """Appends a styled assistant message to the chat history."""
        message = self._format_message("Horoscope AI", text, "#7c3aed")
        self.chat_history.append(message)

    def append_system_message(self, text: str) -> None:
        """Appends a neutral system message to the chat history."""
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
            try:
                result = self.chat_service.ask(self.active_user_id, query)
                self.display_chat_result(result)
            except Exception as exc:
                self.append_system_message(f"Chat request failed: {exc}")
            return

        self.chat_requested.emit(self.active_user_id, query)

    def display_chat_response(self, response: str) -> None:
        """Displays a completed assistant response."""
        self.append_assistant_message(response)

    def display_chat_result(self, result: dict) -> None:
        """Displays the response from a structured chat-service result."""
        source = str(result.get("response_source", "local")).strip().lower()
        if source == "openai":
            self.set_mode_badge("openai")
            self.append_system_message("Response generated with OpenAI refinement.")
        elif result.get("ai_error"):
            self.set_mode_badge("fallback")
            self.append_system_message("OpenAI refinement was unavailable, so local chat was used.")
        else:
            self.set_mode_badge("local")
        self.append_assistant_message(result.get("response", "No response generated."))

    @staticmethod
    def _format_message(speaker: str, text: str, color: str) -> str:
        safe_text = str(text or "").replace("\n", "<br>")
        return (
            f"<div style='margin-bottom: 10px;'>"
            f"<span style='font-weight: bold; color: {color};'>{speaker}:</span> "
            f"<span>{safe_text}</span>"
            f"</div>"
        )
