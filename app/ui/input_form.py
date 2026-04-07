from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QDateEdit, QTimeEdit, QMessageBox, QComboBox
)
from PyQt6.QtCore import pyqtSignal, QDate, QTime

class InputForm(QWidget):
    # Signals to communicate with the Main Window / Controller
    generate_requested = pyqtSignal(dict)
    save_requested = pyqtSignal(dict)
    state_changed = pyqtSignal(str)
    city_changed = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        form_layout = QFormLayout()

        # Input Fields
        self.name_input = QLineEdit()
        self.dob_input = QDateEdit()
        self.dob_input.setCalendarPopup(True)
        self.dob_input.setDate(QDate(1990, 1, 1))
        
        self.tob_input = QTimeEdit()
        self.tob_input.setTime(QTime(12, 0))

        self.state_input = QComboBox()
        self.state_input.addItem("Select State", "")

        self.city_input = QComboBox()
        self.city_input.addItem("Select City", "")
        self.city_input.setEnabled(False)

        self.place_input = QLineEdit()
        self.place_input.setPlaceholderText("Auto-filled from city, or enter manually")

        self.lat_input = QLineEdit()
        self.lat_input.setPlaceholderText("Auto-filled from city, or enter manually")

        self.lon_input = QLineEdit()
        self.lon_input.setPlaceholderText("Auto-filled from city, or enter manually")

        form_layout.addRow("Name:", self.name_input)
        form_layout.addRow("Date of Birth:", self.dob_input)
        form_layout.addRow("Time of Birth:", self.tob_input)
        form_layout.addRow("State:", self.state_input)
        form_layout.addRow("City:", self.city_input)
        form_layout.addRow("Place:", self.place_input)
        form_layout.addRow("Latitude:", self.lat_input)
        form_layout.addRow("Longitude:", self.lon_input)

        layout.addLayout(form_layout)

        # Buttons
        self.btn_generate = QPushButton("Generate Chart")
        self.btn_save = QPushButton("Save User")

        self.btn_generate.clicked.connect(self.on_generate_clicked)
        self.btn_save.clicked.connect(self.on_save_clicked)
        self.state_input.currentIndexChanged.connect(self.on_state_changed)
        self.city_input.currentIndexChanged.connect(self.on_city_changed)

        layout.addWidget(self.btn_generate)
        layout.addWidget(self.btn_save)
        
        layout.addStretch()
        self.setLayout(layout)

    def set_states(self, states: list[str]):
        """Loads the state dropdown with available values."""
        current_state = self.state_input.currentData()
        self.state_input.blockSignals(True)
        self.state_input.clear()
        self.state_input.addItem("Select State", "")
        for state in states:
            self.state_input.addItem(state, state)

        index = self.state_input.findData(current_state)
        self.state_input.setCurrentIndex(index if index >= 0 else 0)
        self.state_input.blockSignals(False)

    def set_cities(self, cities: list[str]):
        """Loads the city dropdown for the currently selected state."""
        self.city_input.blockSignals(True)
        self.city_input.clear()
        self.city_input.addItem("Select City", "")
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
            QMessageBox.warning(self, "Validation Error", "Name is required!")
            return
        self.generate_requested.emit(data)

    def on_save_clicked(self):
        data = self.get_form_data()
        if not data["name"]:
            QMessageBox.warning(self, "Validation Error", "Name is required!")
            return
        self.save_requested.emit(data)
