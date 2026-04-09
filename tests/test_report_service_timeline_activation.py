from __future__ import annotations

import unittest

from app.services.language_manager import LanguageManager

try:
    from app.services.report_service import ReportService
except ModuleNotFoundError:  # pragma: no cover - optional dependency in test env
    ReportService = None  # type: ignore[assignment]


@unittest.skipIf(ReportService is None, "reportlab is not installed in this test environment")
class ReportServiceTimelineActivationTests(unittest.TestCase):
    def _build_service(self) -> ReportService:
        service = ReportService.__new__(ReportService)
        service._language_manager = LanguageManager("en")
        service.styles = ReportService._build_styles(service)
        return service

    def test_timeline_forecast_section_renders_activation_columns(self) -> None:
        service = self._build_service()
        report_data = {
            "timeline_forecast": {
                "timeline": [
                    {
                        "period": "2026-2028",
                        "area": "career",
                        "event": "Career rise",
                        "confidence": 88,
                        "activation_label": "active_now",
                        "source_factors": ["Jupiter Mahadasha supports this period."],
                    }
                ]
            }
        }

        story = service._build_timeline_forecast_section(report_data)

        table = next(item for item in story if hasattr(item, "_cellvalues"))
        headers = table._cellvalues[0]
        self.assertIn("Activation", headers)
        self.assertIn("Source Factors", headers)
        row = table._cellvalues[1]
        self.assertEqual("Active Now", row[3])
        self.assertIn("Jupiter", row[5])


if __name__ == "__main__":
    unittest.main()
