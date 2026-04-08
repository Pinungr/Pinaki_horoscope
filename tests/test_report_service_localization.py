from __future__ import annotations

import unittest

from app.services.language_manager import LanguageManager

try:
    from app.services.report_service import ReportService
except ModuleNotFoundError:  # pragma: no cover - optional dependency in test env
    ReportService = None  # type: ignore[assignment]


@unittest.skipIf(ReportService is None, "reportlab is not installed in this test environment")
class ReportServiceLocalizationTests(unittest.TestCase):
    def _build_service(self, language: str) -> ReportService:
        service = ReportService.__new__(ReportService)
        service._language_manager = LanguageManager(language)
        service.styles = ReportService._build_styles(service)
        return service

    @staticmethod
    def _paragraph_texts(story: list) -> list[str]:
        return [item.getPlainText() for item in story if hasattr(item, "getPlainText")]

    def test_report_sections_render_in_selected_language(self) -> None:
        service = self._build_service("hi")
        report_data = {
            "user": {"name": "Test", "dob": "1990-01-01", "tob": "10:00", "place": "Delhi"},
            "unified_summary": {
                "top_areas": ["career"],
                "time_focus": ["career"],
                "confidence_score": 81,
            },
            "unified_predictions": [],
            "predictions": {},
            "timeline_forecast": {"timeline": []},
            "reasoning": [],
            "key_events": {},
            "timeline": {"timeline": []},
        }

        header_story = service._build_header_section(report_data)
        insight_story = service._build_top_insights_section(report_data)

        self.assertEqual("ऑफलाइन कुंडली रिपोर्ट", header_story[0].getPlainText())
        self.assertIn("मुख्य अंतर्दृष्टि", insight_story[0].getPlainText())


if __name__ == "__main__":
    unittest.main()
