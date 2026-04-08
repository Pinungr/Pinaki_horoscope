from __future__ import annotations

import json
import unittest

from PyQt6.QtWidgets import QApplication

from app.ui.rule_editor_screen import ConditionWidget, RuleEditorScreen


class RuleEditorScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_condition_widget_builds_aspect_condition_dictionary(self) -> None:
        widget = ConditionWidget()

        widget.condition_type_cb.setCurrentText("Aspect")
        widget.from_planet_cb.setCurrentText("Saturn")
        widget.to_planet_cb.setCurrentText("Moon")
        widget.to_house_cb.setCurrentText("5")

        self.assertEqual(
            {
                "aspect_type": "drishti",
                "from_planet": "Saturn",
                "to_planet": "Moon",
                "to_house": 5,
            },
            widget.to_dict(),
        )

    def test_handle_save_emits_aspect_condition_json(self) -> None:
        screen = RuleEditorScreen()
        captured = []
        screen.save_rule_requested.connect(captured.append)

        condition = screen.conditions[0]
        condition.condition_type_cb.setCurrentText("Aspect")
        condition.from_planet_cb.setCurrentText("Saturn")
        condition.to_planet_cb.setCurrentText("Moon")
        condition.to_house_cb.setCurrentText("5")

        screen.result_input.setText("Saturn aspects Moon.")
        screen.handle_save()

        self.assertEqual(1, len(captured))
        self.assertEqual(
            {
                "aspect_type": "drishti",
                "from_planet": "Saturn",
                "to_planet": "Moon",
                "to_house": 5,
            },
            json.loads(captured[0]["condition_json"]),
        )
        self.assertEqual("Saturn aspects Moon.", captured[0]["result_text"])


if __name__ == "__main__":
    unittest.main()
