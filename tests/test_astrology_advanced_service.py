from __future__ import annotations

import unittest
from unittest.mock import patch

from app.models.domain import ChartData
from app.services.astrology_advanced_service import AstrologyAdvancedService


class _StubCache:
    def get(self, namespace: str, user_id: int):
        return None

    def set(self, namespace: str, user_id: int, value) -> None:
        self.last_set = (namespace, user_id, value)


class AstrologyAdvancedServiceTests(unittest.TestCase):
    def test_generate_advanced_data_uses_new_aspect_engine_output_shape(self) -> None:
        chart_data = [
            ChartData(user_id=42, planet_name="Saturn", sign="Gemini", house=3, degree=10.0),
            ChartData(user_id=42, planet_name="Moon", sign="Leo", house=5, degree=12.0),
        ]

        service = AstrologyAdvancedService()
        service.cache = _StubCache()

        with patch.object(service.navamsha_engine, "calculate_navamsha", return_value={"Moon": {"navamsha_sign": "Aries"}}), patch.object(
            service.dasha_engine, "calculate_dasha", return_value=[]
        ), patch("app.engine.event_detector.EventDetectorEngine") as event_detector_cls, patch(
            "app.plugins.plugin_manager.PluginManager"
        ) as plugin_manager_cls:
            event_detector_cls.return_value.detect_events.return_value = []
            plugin_manager_cls.return_value.execute_all.return_value = {}

            advanced_data = service.generate_advanced_data(chart_data, "1990-01-01")

        self.assertEqual(
            [
                {
                    "from_planet": "Saturn",
                    "to_planet": "Moon",
                    "from_house": 3,
                    "to_house": 5,
                    "aspect_type": "drishti",
                }
            ],
            advanced_data["aspects"],
        )
        self.assertEqual({"Moon": {"navamsha_sign": "Aries"}}, advanced_data["navamsha"])
        self.assertEqual([], advanced_data["dasha"])
        self.assertEqual({}, advanced_data["plugins"])

    def test_generate_advanced_data_adds_ui_payload_to_unified_output(self) -> None:
        chart_data = [
            ChartData(user_id=42, planet_name="Saturn", sign="Gemini", house=3, degree=10.0),
            ChartData(user_id=42, planet_name="Moon", sign="Leo", house=5, degree=12.0),
        ]

        class _StubUnifiedEngine:
            def generate_full_analysis(self, chart_data_models, *, dob: str | None = None, language: str = "en"):
                return {
                    "summary": {
                        "top_areas": ["career"],
                        "time_focus": ["career"],
                        "confidence_score": 82,
                    },
                    "predictions": [
                        {
                            "yoga": "Gajakesari Yoga",
                            "area": "career",
                            "strength": "strong",
                            "score": 92,
                            "text": "Career success is visible.",
                            "timing": {"relevance": "high"},
                        }
                    ],
                }

        service = AstrologyAdvancedService()
        service.cache = _StubCache()

        with patch.object(service.navamsha_engine, "calculate_navamsha", return_value={}), patch.object(
            service.dasha_engine, "calculate_dasha", return_value=[]
        ), patch.object(service, "_is_unified_engine_enabled", return_value=True), patch.object(
            service, "_get_unified_engine", return_value=_StubUnifiedEngine()
        ), patch("app.engine.event_detector.EventDetectorEngine") as event_detector_cls, patch(
            "app.plugins.plugin_manager.PluginManager"
        ) as plugin_manager_cls:
            event_detector_cls.return_value.detect_events.return_value = []
            plugin_manager_cls.return_value.execute_all.return_value = {}

            advanced_data = service.generate_advanced_data(chart_data, "1990-01-01")

        ui_payload = advanced_data["unified"]["ui_payload"]
        self.assertIn("summary", ui_payload)
        self.assertEqual(
            [
                {
                    "rule": "gajakesari_yoga",
                    "text": "Career success is visible.",
                    "explanation": "Your career outlook is strong because Gajakesari Yoga is present. The yoga shows a high strength profile (score 92).",
                    "weight": 9,
                }
            ],
            ui_payload["details"],
        )

    def test_generate_advanced_data_passes_selected_language_to_unified_engine(self) -> None:
        chart_data = [
            ChartData(user_id=42, planet_name="Saturn", sign="Gemini", house=3, degree=10.0),
            ChartData(user_id=42, planet_name="Moon", sign="Leo", house=5, degree=12.0),
        ]
        captured: dict[str, str] = {}

        class _StubUnifiedEngine:
            def generate_full_analysis(self, chart_data_models, *, dob: str | None = None, language: str = "en"):
                captured["language"] = language
                return {"summary": {}, "predictions": []}

        service = AstrologyAdvancedService()
        service.cache = _StubCache()

        with patch.object(service.navamsha_engine, "calculate_navamsha", return_value={}), patch.object(
            service.dasha_engine, "calculate_dasha", return_value=[]
        ), patch.object(service, "_is_unified_engine_enabled", return_value=True), patch.object(
            service, "_get_unified_engine", return_value=_StubUnifiedEngine()
        ), patch("app.engine.event_detector.EventDetectorEngine") as event_detector_cls, patch(
            "app.plugins.plugin_manager.PluginManager"
        ) as plugin_manager_cls:
            event_detector_cls.return_value.detect_events.return_value = []
            plugin_manager_cls.return_value.execute_all.return_value = {}

            service.generate_advanced_data(chart_data, "1990-01-01", language="hi")

        self.assertEqual("hi", captured.get("language"))


if __name__ == "__main__":
    unittest.main()
