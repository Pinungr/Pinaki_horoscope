from __future__ import annotations

from typing import Dict

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from app.services.language_manager import LanguageManager
from app.ui.theme import SPACE_8, SPACE_12, SPACE_16, SPACE_24, set_button_icon, set_button_variant


class SettingsScreen(QWidget):
    """Simple settings panel for optional AI enhancement."""

    save_requested = pyqtSignal(dict)
    language_changed = pyqtSignal(str)

    def __init__(self, language_manager: LanguageManager | None = None):
        super().__init__()
        self.language_manager = language_manager or LanguageManager()
        self.init_ui()

    def init_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setContentsMargins(SPACE_24, SPACE_24, SPACE_24, SPACE_24)
        layout.setSpacing(SPACE_16)
        self.form_layout = QFormLayout()
        self.form_layout.setHorizontalSpacing(SPACE_12)
        self.form_layout.setVerticalSpacing(SPACE_12)

        self.title_label = QLabel("Settings")
        self.title_label.setProperty("role", "title")
        self.subtitle_label = QLabel("Configure language and AI refinement behavior.")
        self.subtitle_label.setProperty("role", "subtitle")
        self.subtitle_label.setWordWrap(True)

        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setProperty("role", "subtitle")

        self.language_combo = QComboBox()
        self.language_combo.currentIndexChanged.connect(self._handle_language_changed)

        self.ai_enabled_checkbox = QCheckBox()

        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.show_key_button = QToolButton()
        self.show_key_button.setText("Show")
        self.show_key_button.clicked.connect(self._toggle_api_key_visibility)
        self.api_key_row = QWidget()
        api_key_row_layout = QHBoxLayout()
        api_key_row_layout.setContentsMargins(0, 0, 0, 0)
        api_key_row_layout.setSpacing(SPACE_8)
        api_key_row_layout.addWidget(self.api_key_input, 1)
        api_key_row_layout.addWidget(self.show_key_button)
        self.api_key_row.setLayout(api_key_row_layout)

        self.model_input = QLineEdit()

        self.language_caption = QLabel()
        self.ai_mode_caption = QLabel()
        self.api_key_caption = QLabel()
        self.model_caption = QLabel()

        self.form_layout.addRow(self.language_caption, self.language_combo)
        self.form_layout.addRow(self.ai_mode_caption, self.ai_enabled_checkbox)
        self.form_layout.addRow(self.api_key_caption, self.api_key_row)
        self.form_layout.addRow(self.model_caption, self.model_input)

        self.save_button = QPushButton()
        self.save_button.clicked.connect(self.handle_save)
        set_button_variant(self.save_button, "primary")
        set_button_icon(self.save_button, "save")

        layout.addWidget(self.title_label)
        layout.addWidget(self.subtitle_label)
        layout.addWidget(self.info_label)
        layout.addLayout(self.form_layout)
        layout.addWidget(self.save_button)
        layout.addStretch()
        self.setLayout(layout)
        self.apply_translations()

    def load_settings(self, settings: Dict[str, object]) -> None:
        """Populates the form from persisted settings."""
        self.ai_enabled_checkbox.setChecked(bool(settings.get("ai_enabled", False)))
        self.api_key_input.setText(str(settings.get("openai_api_key", "")))
        self.model_input.setText(str(settings.get("openai_model", "gpt-5-mini")))
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.show_key_button.setText("Show")
        language_code = str(settings.get("language_code", "en") or "en").strip().lower()
        self.language_combo.blockSignals(True)
        index = self.language_combo.findData(language_code)
        self.language_combo.setCurrentIndex(index if index >= 0 else 0)
        self.language_combo.blockSignals(False)

    def handle_save(self) -> None:
        """Validates and emits the current settings payload."""
        model = self.model_input.text().strip() or "gpt-5-mini"
        payload = {
            "ai_enabled": self.ai_enabled_checkbox.isChecked(),
            "openai_api_key": self.api_key_input.text().strip(),
            "openai_model": model,
            "language_code": self.current_language_code(),
        }

        if payload["ai_enabled"] and not payload["openai_api_key"]:
            QMessageBox.information(
                self,
                self._tr("ui.api_key_optional_title"),
                self._tr("ui.api_key_optional_message"),
            )

        self.save_requested.emit(payload)

    def current_language_code(self) -> str:
        return str(self.language_combo.currentData() or "en").strip().lower()

    def apply_translations(self) -> None:
        self.info_label.setText(self._tr("ui.ai_optional_info"))
        self.language_caption.setText(f"{self._tr('ui.language')}:")
        self.ai_mode_caption.setText(f"{self._tr('ui.ai_mode')}:")
        self.api_key_caption.setText(f"{self._tr('ui.openai_api_key')}:")
        self.model_caption.setText(f"{self._tr('ui.model')}:")
        self.ai_enabled_checkbox.setText(self._tr("ui.enable_openai_refinement"))
        self.api_key_input.setPlaceholderText(self._tr("ui.optional_openai_api_key"))
        self.model_input.setPlaceholderText(self._tr("ui.model_placeholder"))
        self.save_button.setText(self._tr("ui.save_settings"))
        self._populate_language_options()

    def _populate_language_options(self) -> None:
        current_code = self.current_language_code() if self.language_combo.count() else "en"
        self.language_combo.blockSignals(True)
        self.language_combo.clear()
        self.language_combo.addItem(self._tr("language.english"), "en")
        self.language_combo.addItem(self._tr("language.hindi"), "hi")
        self.language_combo.addItem(self._tr("language.odia"), "or")
        index = self.language_combo.findData(current_code)
        self.language_combo.setCurrentIndex(index if index >= 0 else 0)
        self.language_combo.blockSignals(False)

    def _handle_language_changed(self) -> None:
        self.language_changed.emit(self.current_language_code())

    def _tr(self, key: str) -> str:
        return self.language_manager.get_text(key)

    def _toggle_api_key_visibility(self) -> None:
        if self.api_key_input.echoMode() == QLineEdit.EchoMode.Password:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.show_key_button.setText("Hide")
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.show_key_button.setText("Show")
