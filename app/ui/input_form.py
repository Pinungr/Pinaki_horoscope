from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QDateEdit, QTimeEdit, QMessageBox, QComboBox
)
from PyQt6.QtCore import pyqtSignal, QDate, QTime
from app.services.language_manager import LanguageManager

class InputForm(QWidget):
    # Signals to communicate with the Main Window / Controller
    generate_requested = pyqtSignal(dict)
    save_requested = pyqtSignal(dict)
    state_changed = pyqtSignal(str)
    city_changed = pyqtSignal(str, str)

    def __init__(self, language_manager: LanguageManager | None = None):
        super().__init__()
        self.language_manager = language_manager or LanguageManager()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        self.form_layout = QFormLayout()

        # Input Fields
        self.name_input = QLineEdit()
        self.dob_input = QDateEdit()
        self.dob_input.setCalendarPopup(True)
        self.dob_input.setDate(QDate(1990, 1, 1))
        
        self.tob_input = QTimeEdit()
        self.tob_input.setTime(QTime(12, 0))

        self.state_input = QComboBox()
        self.state_input.addItem("", "")

        self.city_input = QComboBox()
        self.city_input.addItem("", "")
        self.city_input.setEnabled(False)

        self.place_input = QLineEdit()
        self.lat_input = QLineEdit()
        self.lon_input = QLineEdit()
        
        self.name_label = self.form_layout.addRow
        self.name_caption = self._new_form_label()
        self.dob_caption = self._new_form_label()
        self.tob_caption = self._new_form_label()
        self.state_caption = self._new_form_label()
        self.city_caption = self._new_form_label()
        self.place_caption = self._new_form_label()
        self.lat_caption = self._new_form_label()
        self.lon_caption = self._new_form_label()

        self.form_layout.addRow(self.name_caption, self.name_input)
        self.form_layout.addRow(self.dob_caption, self.dob_input)
        self.form_layout.addRow(self.tob_caption, self.tob_input)
        self.form_layout.addRow(self.state_caption, self.state_input)
        self.form_layout.addRow(self.city_caption, self.city_input)
        self.form_layout.addRow(self.place_caption, self.place_input)
        self.form_layout.addRow(self.lat_caption, self.lat_input)
        self.form_layout.addRow(self.lon_caption, self.lon_input)

        layout.addLayout(self.form_layout)

        # Buttons
        self.btn_generate = QPushButton()
        self.btn_save = QPushButton()

        self.btn_generate.clicked.connect(self.on_generate_clicked)
        self.btn_save.clicked.connect(self.on_save_clicked)
        self.state_input.currentIndexChanged.connect(self.on_state_changed)
        self.city_input.currentIndexChanged.connect(self.on_city_changed)

        layout.addWidget(self.btn_generate)
        layout.addWidget(self.btn_save)
        
        layout.addStretch()
        self.setLayout(layout)
        self.apply_translations()

    def _new_form_label(self):
        from PyQt6.QtWidgets import QLabel
        return QLabel()

    def _tr(self, key: str) -> str:
        return self.language_manager.get_text(key)

    def apply_translations(self) -> None:
        self.name_caption.setText(f"{self._tr('ui.name')}:")
        self.dob_caption.setText(f"{self._tr('ui.date_of_birth')}:")
        self.tob_caption.setText(f"{self._tr('ui.time_of_birth')}:")
        self.state_caption.setText(f"{self._tr('ui.state')}:")
        self.city_caption.setText(f"{self._tr('ui.city')}:")
        self.place_caption.setText(f"{self._tr('ui.place')}:")
        self.lat_caption.setText(f"{self._tr('ui.latitude')}:")
        self.lon_caption.setText(f"{self._tr('ui.longitude')}:")

        placeholder = self._tr("ui.auto_fill_location")
        self.place_input.setPlaceholderText(placeholder)
        self.lat_input.setPlaceholderText(placeholder)
        self.lon_input.setPlaceholderText(placeholder)

        self.btn_generate.setText(self._tr("ui.generate_chart"))
        self.btn_save.setText(self._tr("ui.save_user"))
        self._refresh_combo_placeholders()

    def _refresh_combo_placeholders(self) -> None:
        current_state = self.state_input.currentData()
        current_city = self.city_input.currentData()

        self.state_input.blockSignals(True)
        state_text = self.state_input.itemText(0) if self.state_input.count() else ""
        if not current_state and self.state_input.count():
            self.state_input.setItemText(0, self._tr("ui.select_state"))
        elif self.state_input.count():
            self.state_input.setItemText(0, self._tr("ui.select_state"))
        self.state_input.blockSignals(False)

        self.city_input.blockSignals(True)
        if self.city_input.count():
            self.city_input.setItemText(0, self._tr("ui.select_city"))
        self.city_input.blockSignals(False)

    def set_states(self, states: list[str]):
        """Loads the state dropdown with available values."""
        current_state = self.state_input.currentData()
        self.state_input.blockSignals(True)
        self.state_input.clear()
        self.state_input.addItem(self._tr("ui.select_state"), "")
        for state in states:
            self.state_input.addItem(state, state)

        index = self.state_input.findData(current_state)
        self.state_input.setCurrentIndex(index if index >= 0 else 0)
        self.state_input.blockSignals(False)

    def set_cities(self, cities: list[str]):
        """Loads the city dropdown for the currently selected state."""
        self.city_input.blockSignals(True)
        self.city_input.clear()
        self.city_input.addItem(self._tr("ui.select_city"), "")
        for city in cities:
            self.city_input.addItem(city, city)
        self.city_input.setEnabled(bool(cities))
        self.city_input.setCurrentIndex(0)
        self.city_input.blockSignals(False)

    def set_location_details(self, state: str, city: str, latitude: float, longitude: float):
        """Updates the form with the selected city details."""
        self.place_input.setText(f"{city}, {state}")
        self.lat_input.setText(f"{float(latitude):.6f}")
        self.lon_input.setText(f"{float(longitude):.6f}")

    def clear_location_details(self):
        """Clears auto-filled location fields while preserving user-entered identity data."""
        self.place_input.clear()
        self.lat_input.clear()
        self.lon_input.clear()

    def _selected_state(self) -> str:
        return str(self.state_input.currentData() or "").strip()

    def _selected_city(self) -> str:
        return str(self.city_input.currentData() or "").strip()

    def get_form_data(self) -> dict:
        return {
            "name": self.name_input.text(),
            "dob": self.dob_input.date().toString("yyyy-MM-dd"),
            "tob": self.tob_input.time().toString("HH:mm:ss"),
            "place": self.place_input.text(),
            "latitude": self.lat_input.text(),
            "longitude": self.lon_input.text(),
            "state": self._selected_state(),
            "city": self._selected_city(),
        }

    def on_state_changed(self):
        state = self._selected_state()
        self.set_cities([])
        self.clear_location_details()
        if state:
            self.state_changed.emit(state)

    def on_city_changed(self):
        state = self._selected_state()
        city = self._selected_city()
        if state and city:
            self.city_changed.emit(state, city)

    def on_generate_clicked(self):
        data = self.get_form_data()
        if not data["name"]:
            QMessageBox.warning(self, self._tr("ui.validation_error"), self._tr("ui.name_required"))
            return
        self.generate_requested.emit(data)

    def on_save_clicked(self):
        data = self.get_form_data()
        if not data["name"]:
            QMessageBox.warning(self, self._tr("ui.validation_error"), self._tr("ui.name_required"))
            return
        self.save_requested.emit(data)
