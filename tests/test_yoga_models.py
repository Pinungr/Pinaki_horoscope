from __future__ import annotations

import unittest

from app.models.domain import ChartData
from core.yoga.models import ChartSnapshot, YogaDefinition


class YogaModelTests(unittest.TestCase):
    def test_chart_snapshot_normalizes_chart_rows(self) -> None:
        rows = [
            ChartData(user_id=1, planet_name="Moon", sign="Cancer", house=4, degree=12.5),
            {"Planet": "Jupiter", "Sign": "Cancer", "House": 4, "Degree": 5.0},
            {"planet_name": "BadPlanet", "house": 2},
        ]

        chart = ChartSnapshot.from_rows(rows, metadata={"ayanamsha": "lahiri"})

        self.assertEqual({"moon", "jupiter"}, set(chart.placements.keys()))
        self.assertEqual(4, chart.get("MOON").house)
        self.assertEqual("lahiri", chart.metadata["ayanamsha"])

    def test_yoga_definition_parses_config_driven_payload(self) -> None:
        payload = {
            "id": "gajakesari_yoga",
            "conditions": [
                {"type": "conjunction", "planets": ["Moon", "Jupiter"]},
                {"type": "in_kendra", "planet": "Jupiter"},
            ],
            "strength_rules": [
                {"id": "jupiter_own_sign_bonus", "type": "planet_strength", "planet": "Jupiter", "score": 20},
            ],
            "prediction": {
                "en": "Gajakesari Yoga is present.",
                "hi": "गजकेसरी योग उपस्थित है।",
            },
        }

        yoga = YogaDefinition.from_dict(payload)

        self.assertEqual("gajakesari_yoga", yoga.id)
        self.assertEqual(2, len(yoga.conditions))
        self.assertEqual("conjunction", yoga.conditions[0].type)
        self.assertEqual("in_kendra", yoga.conditions[1].type)
        self.assertEqual(1, len(yoga.strength_rules))
        self.assertEqual("Gajakesari Yoga is present.", yoga.prediction.get_text("en"))
        self.assertEqual("Gajakesari Yoga is present.", yoga.prediction.get_text("fr"))


if __name__ == "__main__":
    unittest.main()
