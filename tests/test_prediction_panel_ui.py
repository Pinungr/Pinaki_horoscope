from __future__ import annotations

import unittest

from PyQt6.QtWidgets import QApplication

from app.services.language_manager import LanguageManager
from app.ui.prediction_panel import PredictionPanel


class PredictionPanelUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_panel_renders_strength_activation_transit_and_concordance(self) -> None:
        panel = PredictionPanel(LanguageManager("en"))
        panel.set_predictions(
            [
                {
                    "area": "career",
                    "confidence": "high",
                    "strength": "strong",
                    "activation_label": "active_now",
                    "agreement_level": "high",
                    "transit": {"support_state": "amplifying"},
                    "final_narrative": "Promise: Career rise. Strength: strong. Timing: active. Caution: monitor.",
                }
            ]
        )

        self.assertEqual(1, len(panel._cards))
        card = panel._cards[0]
        self.assertIn("Strength: Strong", card.signal_row.strength_chip.text())
        self.assertIn("Activation: Active Now", card.signal_row.activation_chip.text())
        self.assertIn("Transit: Amplifying", card.signal_row.transit_chip.text())
        self.assertIn("Concordance: High", card.signal_row.concordance_chip.text())

    def test_explain_toggle_expands_and_collapses_details(self) -> None:
        panel = PredictionPanel(LanguageManager("en"))
        panel.set_predictions([{"area": "career", "summary": "steady trend"}])
        card = panel._cards[0]

        self.assertTrue(card.detail_label.isHidden())
        card.explain_button.click()
        self.assertFalse(card.detail_label.isHidden())
        card.explain_button.click()
        self.assertTrue(card.detail_label.isHidden())

    def test_panel_handles_missing_data_without_crashing(self) -> None:
        panel = PredictionPanel(LanguageManager("en"))
        panel.set_predictions([{"area": "finance"}])

        self.assertEqual(1, len(panel._cards))
        card = panel._cards[0]
        self.assertIn("Unknown", card.signal_row.strength_chip.text())
        self.assertIn("Unknown", card.signal_row.activation_chip.text())
        self.assertIn("Unknown", card.signal_row.concordance_chip.text())
        self.assertTrue(card.summary_label.text())


if __name__ == "__main__":
    unittest.main()
