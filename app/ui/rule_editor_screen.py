import json

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from app.ui.theme import SPACE_8, SPACE_12, SPACE_16, SPACE_24, set_button_icon, set_button_variant


PLANETS = ["Any", "Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu", "Ascendant"]
ASPECT_PLANETS = ["Any", "Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
HOUSES = ["Any"] + [str(i) for i in range(1, 13)]
SIGNS = ["Any", "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]


class ConditionWidget(QWidget):
    """A row representing either a placement condition or an aspect condition."""

    def __init__(self):
        super().__init__()

        layout = QHBoxLayout()
        layout.setContentsMargins(SPACE_8, SPACE_8, SPACE_8, SPACE_8)
        layout.setSpacing(SPACE_8)

        self.condition_type_cb = QComboBox()
        self.condition_type_cb.addItems(["Placement", "Aspect"])

        self.placement_label = QLabel("Placement:")
        self.planet_cb = QComboBox()
        self.planet_cb.addItems(PLANETS)
        self.house_cb = QComboBox()
        self.house_cb.addItems(HOUSES)
        self.sign_cb = QComboBox()
        self.sign_cb.addItems(SIGNS)

        self.aspect_label = QLabel("Aspect:")
        self.from_planet_cb = QComboBox()
        self.from_planet_cb.addItems(ASPECT_PLANETS)
        self.to_planet_cb = QComboBox()
        self.to_planet_cb.addItems(ASPECT_PLANETS)
        self.from_house_cb = QComboBox()
        self.from_house_cb.addItems(HOUSES)
        self.to_house_cb = QComboBox()
        self.to_house_cb.addItems(HOUSES)
        self.aspect_type_cb = QComboBox()
        self.aspect_type_cb.addItems(["drishti"])

        self.btn_remove = QPushButton("X")
        self.btn_remove.setFixedWidth(30)
        set_button_variant(self.btn_remove, "danger")
        set_button_icon(self.btn_remove, "delete")

        layout.addWidget(QLabel("Type:"))
        layout.addWidget(self.condition_type_cb)
        layout.addWidget(self.placement_label)
        layout.addWidget(QLabel("Planet:"))
        layout.addWidget(self.planet_cb)
        layout.addWidget(QLabel("House:"))
        layout.addWidget(self.house_cb)
        layout.addWidget(QLabel("Sign:"))
        layout.addWidget(self.sign_cb)
        layout.addWidget(self.aspect_label)
        layout.addWidget(QLabel("From:"))
        layout.addWidget(self.from_planet_cb)
        layout.addWidget(QLabel("To:"))
        layout.addWidget(self.to_planet_cb)
        layout.addWidget(QLabel("From House:"))
        layout.addWidget(self.from_house_cb)
        layout.addWidget(QLabel("To House:"))
        layout.addWidget(self.to_house_cb)
        layout.addWidget(QLabel("Aspect Type:"))
        layout.addWidget(self.aspect_type_cb)
        layout.addWidget(self.btn_remove)

        self.setLayout(layout)

        self.condition_type_cb.currentTextChanged.connect(self._update_mode_visibility)
        self._update_mode_visibility()

    def _update_mode_visibility(self) -> None:
        is_aspect = self.condition_type_cb.currentText() == "Aspect"

        placement_widgets = [
            self.placement_label,
            self.planet_cb,
            self.house_cb,
            self.sign_cb,
        ]
        aspect_widgets = [
            self.aspect_label,
            self.from_planet_cb,
            self.to_planet_cb,
            self.from_house_cb,
            self.to_house_cb,
            self.aspect_type_cb,
        ]

        for widget in placement_widgets:
            widget.setVisible(not is_aspect)
        for widget in aspect_widgets:
            widget.setVisible(is_aspect)

        labels = []
        for index in range(self.layout().count()):
            item = self.layout().itemAt(index)
            widget = item.widget() if item is not None else None
            if isinstance(widget, QLabel):
                labels.append(widget)

        placement_label_texts = {"Placement:", "Planet:", "House:", "Sign:"}
        aspect_label_texts = {"Aspect:", "From:", "To:", "From House:", "To House:", "Aspect Type:"}
        for label in labels:
            if label.text() in placement_label_texts:
                label.setVisible(not is_aspect)
            elif label.text() in aspect_label_texts:
                label.setVisible(is_aspect)

    def to_dict(self):
        if self.condition_type_cb.currentText() == "Aspect":
            cond = {"aspect_type": self.aspect_type_cb.currentText()}
            if self.from_planet_cb.currentText() != "Any":
                cond["from_planet"] = self.from_planet_cb.currentText()
            if self.to_planet_cb.currentText() != "Any":
                cond["to_planet"] = self.to_planet_cb.currentText()
            if self.from_house_cb.currentText() != "Any":
                cond["from_house"] = int(self.from_house_cb.currentText())
            if self.to_house_cb.currentText() != "Any":
                cond["to_house"] = int(self.to_house_cb.currentText())
            return cond

        cond = {}
        if self.planet_cb.currentText() != "Any":
            cond["planet"] = self.planet_cb.currentText()
        if self.house_cb.currentText() != "Any":
            cond["house"] = int(self.house_cb.currentText())
        if self.sign_cb.currentText() != "Any":
            cond["sign"] = self.sign_cb.currentText()
        return cond

    def has_meaningful_selection(self) -> bool:
        condition = self.to_dict()
        if self.condition_type_cb.currentText() == "Aspect":
            return any(key != "aspect_type" for key in condition)
        return bool(condition)

    def reset(self) -> None:
        self.condition_type_cb.setCurrentIndex(0)
        self.planet_cb.setCurrentIndex(0)
        self.house_cb.setCurrentIndex(0)
        self.sign_cb.setCurrentIndex(0)
        self.from_planet_cb.setCurrentIndex(0)
        self.to_planet_cb.setCurrentIndex(0)
        self.from_house_cb.setCurrentIndex(0)
        self.to_house_cb.setCurrentIndex(0)
        self.aspect_type_cb.setCurrentIndex(0)
        self._update_mode_visibility()


class RuleEditorScreen(QWidget):
    save_rule_requested = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.conditions = []
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(SPACE_24, SPACE_24, SPACE_24, SPACE_24)
        main_layout.setSpacing(SPACE_16)

        self.title_label = QLabel("Rule Editor")
        self.title_label.setProperty("role", "title")
        self.subtitle_label = QLabel("Create reusable prediction rules with clear condition logic.")
        self.subtitle_label.setProperty("role", "subtitle")
        self.subtitle_label.setWordWrap(True)
        main_layout.addWidget(self.title_label)
        main_layout.addWidget(self.subtitle_label)

        group_layout = QHBoxLayout()
        group_layout.setSpacing(SPACE_8)
        group_layout.addWidget(QLabel("Rule Match Logic:"))
        self.logic_cb = QComboBox()
        self.logic_cb.addItems(["AND (All must match)", "OR (Any can match)"])
        group_layout.addWidget(self.logic_cb)
        group_layout.addStretch()
        main_layout.addLayout(group_layout)

        self.conditions_container = QWidget()
        self.conditions_layout = QVBoxLayout()
        self.conditions_layout.setSpacing(SPACE_12)
        self.conditions_layout.setAlignment(Qt.AlignmentFlag.AlignTop) if hasattr(Qt, "AlignmentFlag") else self.conditions_layout.setAlignment(0x0020)
        self.conditions_container.setLayout(self.conditions_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.conditions_container)

        main_layout.addWidget(QLabel("Conditions:"))
        main_layout.addWidget(scroll)

        self.btn_add_condition = QPushButton("+ Add Condition")
        self.btn_add_condition.clicked.connect(self.add_condition_row)
        set_button_variant(self.btn_add_condition, "ghost")
        set_button_icon(self.btn_add_condition, "add")
        main_layout.addWidget(self.btn_add_condition)

        self.add_condition_row()

        form_layout = QFormLayout()

        self.result_input = QLineEdit()
        self.result_input.setPlaceholderText("e.g. This gives strong leadership...")
        self.result_input.setMinimumHeight(40)

        self.result_key_input = QLineEdit()
        self.result_key_input.setPlaceholderText("Optional: prediction.message.sun_first_house_vitality")

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
        form_layout.addRow("Result Key:", self.result_key_input)
        form_layout.addRow("Category:", self.category_input)
        form_layout.addRow("Effect:", self.effect_input)
        form_layout.addRow("Weight:", self.weight_input)
        form_layout.addRow("Priority (Higher = First):", self.priority_input)

        main_layout.addLayout(form_layout)

        self.btn_save = QPushButton("Save Astrology Rule")
        self.btn_save.setMinimumHeight(40)
        self.btn_save.clicked.connect(self.handle_save)
        set_button_variant(self.btn_save, "primary")
        set_button_icon(self.btn_save, "save")
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
        result_text = self.result_input.text().strip()
        if not result_text:
            QMessageBox.warning(self, "Validation", "Result text is required.")
            return

        valid_conds = []
        for row in self.conditions:
            if row.has_meaningful_selection():
                valid_conds.append(row.to_dict())

        if not valid_conds:
            QMessageBox.warning(self, "Validation", "At least one condition must be specified.")
            return

        if len(valid_conds) == 1:
            json_cond = valid_conds[0]
        else:
            logic_op = "AND" if "AND" in self.logic_cb.currentText() else "OR"
            json_cond = {logic_op: valid_conds}

        self.save_rule_requested.emit(
            {
                "condition_json": json.dumps(json_cond),
                "result_text": result_text,
                "result_key": self.result_key_input.text().strip().replace("prediction.message.", ""),
                "category": self.category_input.text().strip(),
                "effect": self.effect_input.currentText().strip().lower(),
                "weight": self.weight_input.value(),
                "priority": self.priority_input.value(),
            }
        )

    def clear_form(self):
        self.result_input.clear()
        self.result_key_input.clear()
        self.category_input.clear()
        self.effect_input.setCurrentIndex(0)
        self.weight_input.setValue(1.0)
        self.priority_input.setValue(10)
        while len(self.conditions) > 1:
            self.remove_condition_row(self.conditions[-1])
        if self.conditions:
            self.conditions[0].reset()
