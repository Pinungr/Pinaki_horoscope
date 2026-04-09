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

    def test_generate_advanced_data_exposes_timeline_forecast_with_activation_labels(self) -> None:
        chart_data = [
            ChartData(user_id=42, planet_name="Saturn", sign="Gemini", house=3, degree=10.0),
            ChartData(user_id=42, planet_name="Moon", sign="Leo", house=5, degree=12.0),
        ]

        class _StubUnifiedEngine:
            def generate_full_analysis(self, chart_data_models, *, dob: str | None = None, language: str = "en"):
                return {
                    "summary": {},
                    "predictions": [
                        {
                            "yoga": "Raj Yoga",
                            "area": "career",
                            "strength": "strong",
                            "score": 90,
                            "timing": {"mahadasha": "Jupiter", "antardasha": "Moon", "activation_score": 82},
                        }
                    ],
                }

        service = AstrologyAdvancedService()
        service.cache = _StubCache()

        forecast_stub = {
            "timeline": [
                {
                    "period": "2026-2028",
                    "activation_label": "active_now",
                    "activation_score": 84,
                    "source_factors": ["Jupiter Mahadasha supports the promise."],
                }
            ]
        }

        with patch.object(service.navamsha_engine, "calculate_navamsha", return_value={}), patch.object(
            service.dasha_engine, "calculate_dasha", return_value=[]
        ), patch.object(service, "_is_unified_engine_enabled", return_value=True), patch.object(
            service, "_get_unified_engine", return_value=_StubUnifiedEngine()
        ), patch.object(
            service.timeline_service, "build_timeline_forecast", return_value=forecast_stub
        ), patch("app.engine.event_detector.EventDetectorEngine") as event_detector_cls, patch(
            "app.plugins.plugin_manager.PluginManager"
        ) as plugin_manager_cls:
            event_detector_cls.return_value.detect_events.return_value = []
            plugin_manager_cls.return_value.execute_all.return_value = {}

            advanced_data = service.generate_advanced_data(chart_data, "1990-01-01")

        self.assertEqual(forecast_stub, advanced_data["timeline_forecast"])
        self.assertEqual(forecast_stub, advanced_data["unified"]["timeline_forecast"])

    def test_generate_advanced_data_exposes_dual_reference_transits(self) -> None:
        chart_data = [
            ChartData(user_id=42, planet_name="Ascendant", sign="Aries", house=1, degree=0.0),
            ChartData(user_id=42, planet_name="Moon", sign="Cancer", house=4, degree=12.0),
            ChartData(user_id=42, planet_name="Saturn", sign="Gemini", house=3, degree=10.0),
        ]
        transit_stub = {
            "reference": "both",
            "target_time": "2026-04-09T00:00:00",
            "transits": {"sun": {"house_from_reference": 1, "sign": "cancer", "is_retrograde": False}},
            "from_lagna": {"sun": {"house_from_reference": 4, "sign": "cancer", "is_retrograde": False}},
            "from_moon": {"sun": {"house_from_reference": 1, "sign": "cancer", "is_retrograde": False}},
            "transit_matrix": {
                "sun": {
                    "transit_planet": "sun",
                    "from_lagna": {
                        "house_position": 4,
                        "effects": ["Supportive"],
                        "strength_modifiers": ["supportive_house_context"],
                    },
                    "from_moon": {
                        "house_position": 1,
                        "effects": ["Supportive"],
                        "strength_modifiers": ["supportive_house_context"],
                    },
                }
            },
        }

        service = AstrologyAdvancedService()
        service.cache = _StubCache()

        with patch.object(service.navamsha_engine, "calculate_navamsha", return_value={}), patch.object(
            service.dasha_engine, "calculate_dasha", return_value=[]
        ), patch.object(service.transit_engine, "calculate_transits", return_value=transit_stub), patch(
            "app.engine.event_detector.EventDetectorEngine"
        ) as event_detector_cls, patch("app.plugins.plugin_manager.PluginManager") as plugin_manager_cls:
            event_detector_cls.return_value.detect_events.return_value = []
            plugin_manager_cls.return_value.execute_all.return_value = {}

            advanced_data = service.generate_advanced_data(chart_data, "1990-01-01")

        self.assertEqual("both", advanced_data["transits"]["reference"])
        self.assertIn("from_lagna", advanced_data["transits"])
        self.assertIn("from_moon", advanced_data["transits"])
        self.assertIn("transit_matrix", advanced_data["transits"])
        self.assertIn("from_lagna", advanced_data["transits"]["transit_matrix"]["sun"])
        self.assertIn("from_moon", advanced_data["transits"]["transit_matrix"]["sun"])

    def test_generate_advanced_data_adds_d10_validation_to_career_predictions(self) -> None:
        chart_data = [
            ChartData(user_id=42, planet_name="Ascendant", sign="Aries", house=1, degree=0.0),
            ChartData(user_id=42, planet_name="Moon", sign="Cancer", house=4, degree=12.0),
            ChartData(user_id=42, planet_name="Saturn", sign="Gemini", house=3, degree=10.0),
        ]

        class _StubUnifiedEngine:
            def generate_full_analysis(self, chart_data_models, *, dob: str | None = None, language: str = "en"):
                return {
                    "summary": {},
                    "predictions": [
                        {
                            "yoga": "Raj Yoga",
                            "area": "career",
                            "strength": "strong",
                            "score": 88,
                            "text": "Career promise is active.",
                            "timing": {"mahadasha": "Saturn", "relevance": "high"},
                        }
                    ],
                }

        d10_stub = {
            "ascendant_sign": "aries",
            "rows": [{"planet_name": "Saturn", "sign": "libra", "house": 7, "degree": 10.0}],
            "placements": {"saturn": {"sign": "libra", "house": 7, "degree": 10.0}},
        }
        d10_validation_stub = {
            "status": "confirm",
            "factors": ["D10 10th lord well placed."],
            "multiplier": 1.12,
            "score": 1.2,
        }

        service = AstrologyAdvancedService()
        service.cache = _StubCache()

        with patch.object(service.navamsha_engine, "calculate_navamsha", return_value={}), patch.object(
            service.dasha_engine, "calculate_dasha", return_value=[]
        ), patch.object(service.varga_engine, "get_d10_chart", return_value=d10_stub), patch.object(
            service.prediction_service, "evaluate_d10_career_validation", return_value=d10_validation_stub
        ), patch.object(service, "_is_unified_engine_enabled", return_value=True), patch.object(
            service, "_get_unified_engine", return_value=_StubUnifiedEngine()
        ), patch("app.engine.event_detector.EventDetectorEngine") as event_detector_cls, patch(
            "app.plugins.plugin_manager.PluginManager"
        ) as plugin_manager_cls:
            event_detector_cls.return_value.detect_events.return_value = []
            plugin_manager_cls.return_value.execute_all.return_value = {}

            advanced_data = service.generate_advanced_data(chart_data, "1990-01-01")

        self.assertEqual(d10_stub, advanced_data["dashamsha"])
        self.assertEqual(d10_validation_stub, advanced_data["d10_career_validation"])
        career_row = advanced_data["unified"]["predictions"][0]
        self.assertEqual("confirm", career_row["d10_status"])
        self.assertIn("D10 10th lord well placed.", career_row["d10_evidence"])
        self.assertEqual("confirm", career_row["timing"]["d10_status"])

    def test_generate_advanced_data_adds_concordance_defaults_for_unified_predictions(self) -> None:
        chart_data = [
            ChartData(user_id=42, planet_name="Ascendant", sign="Aries", house=1, degree=0.0),
            ChartData(user_id=42, planet_name="Moon", sign="Cancer", house=4, degree=12.0),
            ChartData(user_id=42, planet_name="Saturn", sign="Gemini", house=3, degree=10.0),
        ]

        class _StubUnifiedEngine:
            def generate_full_analysis(self, chart_data_models, *, dob: str | None = None, language: str = "en"):
                return {
                    "summary": {},
                    "predictions": [
                        {
                            "yoga": "Raj Yoga",
                            "area": "career",
                            "strength": "strong",
                            "score": 88,
                            "text": "Career promise is active.",
                            "timing": {"mahadasha": "Saturn", "relevance": "high"},
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

        career_row = advanced_data["unified"]["predictions"][0]
        self.assertEqual(0.5, career_row["concordance_score"])
        self.assertEqual("medium", career_row["agreement_level"])
        self.assertEqual([], career_row["concordance_factors"])
        self.assertEqual(0.5, career_row["timing"]["concordance_score"])


if __name__ == "__main__":
    unittest.main()
