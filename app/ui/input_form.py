from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, 
    QPushButton, QLabel, QDateEdit, QTimeEdit, QMessageBox
)
from PyQt6.QtCore import pyqtSignal, QDate, QTime

class InputForm(QWidget):
    # Signals to communicate with the Main Window / Controller
    generate_requested = pyqtSignal(dict)
    save_requested = pyqtSignal(dict)

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
        
        self.place_input = QLineEdit()
        self.place_input.setPlaceholderText("e.g. New Delhi")

        self.lat_input = QLineEdit()
        self.lat_input.setPlaceholderText("e.g. 28.6139")
        
        self.lon_input = QLineEdit()
        self.lon_input.setPlaceholderText("e.g. 77.2090")

        form_layout.addRow("Name:", self.name_input)
        form_layout.addRow("Date of Birth:", self.dob_input)
        form_layout.addRow("Time of Birth:", self.tob_input)
        form_layout.addRow("Place:", self.place_input)
        form_layout.addRow("Latitude:", self.lat_input)
        form_layout.addRow("Longitude:", self.lon_input)

        layout.addLayout(form_layout)

        # Buttons
        self.btn_generate = QPushButton("Generate Chart")
        self.btn_save = QPushButton("Save User")

        self.btn_generate.clicked.connect(self.on_generate_clicked)
        self.btn_save.clicked.connect(self.on_save_clicked)

        layout.addWidget(self.btn_generate)
        layout.addWidget(self.btn_save)
        
        layout.addStretch()
        self.setLayout(layout)

    def get_form_data(self) -> dict:
        return {
            "name": self.name_input.text(),
            "dob": self.dob_input.date().toString("yyyy-MM-dd"),
            "tob": self.tob_input.time().toString("HH:mm:ss"),
            "place": self.place_input.text(),
            "latitude": self.lat_input.text() or "0.0",
            "longitude": self.lon_input.text() or "0.0"
        }

    def on_generate_clicked(self):
        data = self.get_form_data()
        if not data["name"] or not data["place"]:
            QMessageBox.warning(self, "Validation Error", "Name and Place are required!")
            return
        self.generate_requested.emit(data)

    def on_save_clicked(self):
        data = self.get_form_data()
        if not data["name"] or not data["place"]:
            QMessageBox.warning(self, "Validation Error", "Name and Place are required!")
            return
        self.save_requested.emit(data)
