from __future__ import annotations

from typing import Dict

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SettingsScreen(QWidget):
    """Simple settings panel for optional AI enhancement."""

    save_requested = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        self.info_label = QLabel(
            "AI enhancement is optional. Leave it off to use the local horoscope chat only."
        )
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #556070; margin-bottom: 8px;")

        self.ai_enabled_checkbox = QCheckBox("Enable OpenAI refinement")

        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("Optional: paste your OpenAI API key")

        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("e.g. gpt-5-mini")

        form_layout.addRow("AI Mode:", self.ai_enabled_checkbox)
        form_layout.addRow("OpenAI API Key:", self.api_key_input)
        form_layout.addRow("Model:", self.model_input)

        self.save_button = QPushButton("Save Settings")
        self.save_button.clicked.connect(self.handle_save)

        layout.addWidget(self.info_label)
        layout.addLayout(form_layout)
        layout.addWidget(self.save_button)
        layout.addStretch()
        self.setLayout(layout)

    def load_settings(self, settings: Dict[str, object]) -> None:
        """Populates the form from persisted settings."""
        self.ai_enabled_checkbox.setChecked(bool(settings.get("ai_enabled", False)))
        self.api_key_input.setText(str(settings.get("openai_api_key", "")))
        self.model_input.setText(str(settings.get("openai_model", "gpt-5-mini")))

    def handle_save(self) -> None:
        """Validates and emits the current settings payload."""
        model = self.model_input.text().strip() or "gpt-5-mini"
        payload = {
            "ai_enabled": self.ai_enabled_checkbox.isChecked(),
            "openai_api_key": self.api_key_input.text().strip(),
            "openai_model": model,
        }

        if payload["ai_enabled"] and not payload["openai_api_key"]:
            QMessageBox.information(
                self,
                "API Key Optional",
                "AI mode is enabled, but no API key is saved here. "
                "The app will fall back to the OPENAI_API_KEY environment variable if available.",
            )

        self.save_requested.emit(payload)
