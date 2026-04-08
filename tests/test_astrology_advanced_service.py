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


if __name__ == "__main__":
    unittest.main()
