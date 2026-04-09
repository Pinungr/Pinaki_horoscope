from __future__ import annotations

import unittest

from PyQt6.QtWidgets import QApplication

from app.ui.widgets.timeline_widget import TimelineWidget


class TimelineWidgetUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_forecast_view_shows_activation_badge_and_transition_hint(self) -> None:
        widget = TimelineWidget()
        widget.resize(980, 560)
        widget.set_timeline_data(
            {
                "mode": "forecast",
                "timeline": [
                    {
                        "period": "2026-2027",
                        "area": "career",
                        "event": "Career acceleration phase",
                        "confidence": 87,
                        "activation_label": "upcoming",
                        "activation_trend": "rising",
                        "agreement_level": "high",
                        "transit_support_state": "amplifying",
                        "start": "2026-01-01",
                        "end": "2027-01-01",
                    }
                ],
            }
        )

        texts = self._scene_texts(widget)
        self.assertTrue(any("Activation: Upcoming" in text for text in texts))
        self.assertTrue(any("Upcoming -> Active" in text for text in texts))
        self.assertTrue(any("Transit: Amplifying" in text for text in texts))
        self.assertTrue(any("Concordance: High" in text for text in texts))

    def test_forecast_view_handles_missing_data_gracefully(self) -> None:
        widget = TimelineWidget()
        widget.resize(920, 520)
        widget.set_timeline_data(
            {
                "mode": "forecast",
                "timeline": [{"area": "finance", "start": "2028-01-01", "end": "2028-12-31"}],
            }
        )

        texts = self._scene_texts(widget)
        self.assertTrue(any("Activation:" in text for text in texts))
        self.assertTrue(widget.sceneRect().width() > 0)
        self.assertTrue(widget.sceneRect().height() > 0)

    @staticmethod
    def _scene_texts(widget: TimelineWidget) -> list[str]:
        collected: list[str] = []
        for item in widget.scene().items():
            text_getter = getattr(item, "text", None)
            if callable(text_getter):
                text = str(text_getter()).strip()
                if text:
                    collected.append(text)
        return collected


if __name__ == "__main__":
    unittest.main()
