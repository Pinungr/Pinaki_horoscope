from __future__ import annotations

import unittest

from app.services.language_manager import LanguageManager

try:
    from app.services.report_service import ReportService
except ModuleNotFoundError:  # pragma: no cover - optional dependency in test env
    ReportService = None  # type: ignore[assignment]


@unittest.skipIf(ReportService is None, "reportlab is not installed in this test environment")
class ReportServiceParashariNarrativeTests(unittest.TestCase):
    def _build_service(self) -> ReportService:
        service = ReportService.__new__(ReportService)
        service._language_manager = LanguageManager("en")
        service.styles = ReportService._build_styles(service)
        return service

    def test_predictions_section_prefers_shared_parashari_narrative(self) -> None:
        service = self._build_service()
        report_data = {
            "unified_predictions": [
                {
                    "area": "career",
                    "yoga": "Raj Yoga",
                    "strength": "strong",
                    "score": 90,
                    "final_narrative": (
                        "Promise: Career outcomes are indicated through Raj Yoga. "
                        "Strength: strong bala and supportive varga. "
                        "Timing: Jupiter-Venus window is active. "
                        "Caution: monitor lower-priority conflicting signals."
                    ),
                    "strength_score": 82,
                    "agreement_level": "high",
                    "concordance_score": 0.87,
                    "concordance_factors": ["D1 and D10 are aligned."],
                    "karaka_impact": ["Natural significator supports career rise."],
                    "refined_text": "Legacy summary text should not be shown first.",
                    "resolution": {
                        "dominant_factor": "dasha_activation",
                        "dominant_outcome": "valid",
                    },
                    "timing": {
                        "mahadasha": "Jupiter",
                        "antardasha": "Venus",
                        "activation_level": "high",
                        "dasha_evidence": ["Jupiter-Venus window is active."],
                    },
                    "transit": {"support_state": "amplifying", "source_factors": ["Transit amplifies results."]},
                }
            ]
        }

        story = service._build_predictions_section(report_data)
        paragraphs = [item.getPlainText() for item in story if hasattr(item, "getPlainText")]
        joined = " ".join(paragraphs)

        self.assertIn("Why this is predicted", joined)
        self.assertIn("Strength of indication", joined)
        self.assertIn("When it may manifest", joined)
        self.assertIn("Caution & limitations", joined)
        self.assertIn("Career outcomes are indicated through Raj Yoga.", joined)
        self.assertIn("Reasoning details", joined)
        self.assertIn("Strength explanation", joined)
        self.assertIn("Dasha activation", joined)
        self.assertIn("Transit trigger", joined)
        self.assertIn("Conflict resolution", joined)
        self.assertIn("Concordance summary", joined)
        self.assertNotIn("Legacy summary text should not be shown first.", joined)

        self.assertLess(joined.find("Why this is predicted"), joined.find("Strength of indication"))
        self.assertLess(joined.find("Strength of indication"), joined.find("When it may manifest"))
        self.assertLess(joined.find("When it may manifest"), joined.find("Caution & limitations"))

    def test_predictions_section_handles_missing_fields_with_controlled_fallback(self) -> None:
        service = self._build_service()
        report_data = {
            "unified_predictions": [
                {
                    "area": "finance",
                    "score": 54,
                    "text": "Measured progress in financial matters.",
                }
            ]
        }

        story = service._build_predictions_section(report_data)
        paragraphs = [item.getPlainText() for item in story if hasattr(item, "getPlainText")]
        joined = " ".join(paragraphs)

        self.assertIn("Measured progress in financial matters.", joined)
        self.assertIn("Strength details are not available.", joined)
        self.assertIn("Dasha details are not available.", joined)
        self.assertIn("Conflict resolution details are not available.", joined)
        self.assertNotIn("prediction.parashari", joined)


if __name__ == "__main__":
    unittest.main()
