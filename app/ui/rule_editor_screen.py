import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, 
    QLineEdit, QPushButton, QLabel, QSpinBox, QDoubleSpinBox, QScrollArea,
    QMessageBox, QFormLayout
)
from PyQt6.QtCore import pyqtSignal, Qt

class ConditionWidget(QWidget):
    """A row representing a single logic condition (Planet + House + Sign)"""
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.planet_cb = QComboBox()
        self.planet_cb.addItems(["Any", "Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu", "Ascendant"])
        
        self.house_cb = QComboBox()
        self.house_cb.addItems(["Any"] + [str(i) for i in range(1, 13)])
        
        self.sign_cb = QComboBox()
        self.sign_cb.addItems(["Any", "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"])
        
        self.btn_remove = QPushButton("X")
        self.btn_remove.setFixedWidth(30)
        
        layout.addWidget(QLabel("Planet:"))
        layout.addWidget(self.planet_cb)
        layout.addWidget(QLabel("House:"))
        layout.addWidget(self.house_cb)
        layout.addWidget(QLabel("Sign:"))
        layout.addWidget(self.sign_cb)
        layout.addWidget(self.btn_remove)
        
        self.setLayout(layout)
        
    def to_dict(self):
        cond = {}
        if self.planet_cb.currentText() != "Any":
            cond["planet"] = self.planet_cb.currentText()
        if self.house_cb.currentText() != "Any":
            cond["house"] = int(self.house_cb.currentText())
        if self.sign_cb.currentText() != "Any":
            cond["sign"] = self.sign_cb.currentText()
        return cond

class RuleEditorScreen(QWidget):
    # Sends dictionary representing Rule configuration to controller
    save_rule_requested = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.conditions = []
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        
        # --- Logic Group ---
        group_layout = QHBoxLayout()
        group_layout.addWidget(QLabel("Rule Match Logic:"))
        self.logic_cb = QComboBox()
        self.logic_cb.addItems(["AND (All must match)", "OR (Any can match)"])
        group_layout.addWidget(self.logic_cb)
        # Adds spacer
        group_layout.addStretch()
        main_layout.addLayout(group_layout)

        # --- Conditions Scroll Area ---
        self.conditions_container = QWidget()
        self.conditions_layout = QVBoxLayout()
        self.conditions_layout.setAlignment(Qt.AlignmentFlag.AlignTop) if hasattr(Qt, 'AlignmentFlag') else self.conditions_layout.setAlignment(0x0020)
        self.conditions_container.setLayout(self.conditions_layout)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.conditions_container)
        
        main_layout.addWidget(QLabel("Conditions:"))
        main_layout.addWidget(scroll)

        self.btn_add_condition = QPushButton("+ Add Condition")
        self.btn_add_condition.clicked.connect(self.add_condition_row)
        main_layout.addWidget(self.btn_add_condition)

        # Initialize with one empty condition
        self.add_condition_row()

        # --- Metadata Area ---
        form_layout = QFormLayout()
        
        self.result_input = QLineEdit()
        self.result_input.setPlaceholderText("e.g. This gives strong leadership...")
        self.result_input.setMinimumHeight(40)
        
        self.category_input = QLineEdit()
        self.category_input.setPlaceholderText("e.g. Yoga, General")

        self.effect_input = QComboBox()
        self.effect_input.addItems(["Positive", "Negative"])

        self.weight_input = QDoubleSpinBox()
        self.weight_input.setRange(0.1, 10.0)
        self.weight_input.setSingleStep(0.1)
        self.weight_input.setValue(1.0)
        
        self.priority_input = QSpinBox()
        self.priority_input.setRange(0, 1000)
        self.priority_input.setValue(10)
        
        form_layout.addRow("Result Text:", self.result_input)
        form_layout.addRow("Category:", self.category_input)
        form_layout.addRow("Effect:", self.effect_input)
        form_layout.addRow("Weight:", self.weight_input)
        form_layout.addRow("Priority (Higher = First):", self.priority_input)
        
        main_layout.addLayout(form_layout)

        # --- Save Button ---
        self.btn_save = QPushButton("Save Astrology Rule")
        self.btn_save.setMinimumHeight(40)
        self.btn_save.clicked.connect(self.handle_save)
        main_layout.addWidget(self.btn_save)

        self.setLayout(main_layout)

    def add_condition_row(self):
        row = ConditionWidget()
        row.btn_remove.clicked.connect(lambda: self.remove_condition_row(row))
        self.conditions.append(row)
        self.conditions_layout.addWidget(row)

    def remove_condition_row(self, row: ConditionWidget):
        if len(self.conditions) <= 1:
            QMessageBox.warning(self, "Validation", "You must have at least one condition.")
            return
        self.conditions_layout.removeWidget(row)
        self.conditions.remove(row)
        row.deleteLater()

    def handle_save(self):
        # 1. Gather Result
        result_text = self.result_input.text().strip()
        if not result_text:
            QMessageBox.warning(self, "Validation", "Result text is required.")
            return

        # 2. Gather Conditions
        valid_conds = []
        for row in self.conditions:
            cd = row.to_dict()
            if cd: # only append if at least one dropdown was changed from "Any"
                valid_conds.append(cd)

        if not valid_conds:
            QMessageBox.warning(self, "Validation", "At least one condition must be specified.")
            return

        # 3. Build JSON strictly compliant with Rule Engine
        if len(valid_conds) == 1:
            json_cond = valid_conds[0]
        else:
            logic_op = "AND" if "AND" in self.logic_cb.currentText() else "OR"
            json_cond = {logic_op: valid_conds}

        # Emitting
        self.save_rule_requested.emit({
            "condition_json": json.dumps(json_cond),
            "result_text": result_text,
            "category": self.category_input.text().strip(),
            "effect": self.effect_input.currentText().strip().lower(),
            "weight": self.weight_input.value(),
            "priority": self.priority_input.value()
        })
        
    def clear_form(self):
        self.result_input.clear()
        self.category_input.clear()
        self.effect_input.setCurrentIndex(0)
        self.weight_input.setValue(1.0)
        self.priority_input.setValue(10)
        while len(self.conditions) > 1:
            self.remove_condition_row(self.conditions[-1])
        # Reset first row
        if self.conditions:
            self.conditions[0].planet_cb.setCurrentIndex(0)
            self.conditions[0].house_cb.setCurrentIndex(0)
            self.conditions[0].sign_cb.setCurrentIndex(0)
