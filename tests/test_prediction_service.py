from __future__ import annotations

import unittest
from unittest.mock import patch
import sys

from app.models.domain import ChartData, Rule
from app.repositories.database_manager import DatabaseManager
from app.repositories.rule_repo import RuleRepository
from app.services.horoscope_service import HoroscopeService


class HoroscopePredictionServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from tests.test_support import get_engine_dependency_stubs
        cls.module_patcher = patch.dict(sys.modules, get_engine_dependency_stubs())
        cls.module_patcher.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.module_patcher.stop()

    def setUp(self) -> None:
        from tests.test_support import build_temp_db_path, cleanup_temp_db
        self.build_temp_db_path = build_temp_db_path
        self.cleanup_temp_db = cleanup_temp_db
        self.db_path = build_temp_db_path("test_prediction_service")
        self.db_manager = DatabaseManager(self.db_path)
        self.db_manager.initialize_schema()
        self.rule_repo = RuleRepository(self.db_manager)
        self.service = HoroscopeService(self.db_manager)

        self.chart_rows = [
            ChartData(user_id=1, planet_name="Moon", sign="Cancer", house=10, degree=12.5),
            ChartData(user_id=1, planet_name="Saturn", sign="Aquarius", house=10, degree=18.2),
            ChartData(user_id=1, planet_name="Jupiter", sign="Taurus", house=2, degree=5.0),
        ]

    def tearDown(self) -> None:
        self.cleanup_temp_db(self.db_path)

    def test_evaluate_chart_predictions_balances_positive_and_negative_rules(self) -> None:
        rules = [
            Rule(
                condition_json='{"planet": "Moon", "house": 10}',
                result_text="Career growth is strongly indicated.",
                result_key="career_growth_strong",
                category="career",
                weight=1.5,
                confidence="high",
            ),
            Rule(
                condition_json='{"planet": "Saturn", "house": 10}',
                result_text="Career progress may feel delayed.",
                result_key="career_progress_delayed",
                category="career",
                effect="negative",
                weight=0.6,
                confidence="medium",
            ),
            Rule(
                condition_json='{"planet": "Jupiter", "house": 2}',
                result_text="Financial progress improves steadily.",
                category="finance",
                weight=1.1,
                confidence="high",
            ),
        ]
        for rule in rules:
            self.rule_repo.save(rule)

        chart_rows = list(self.chart_rows) + [
            ChartData(user_id=1, planet_name="Ascendant", sign="Aries", house=1, degree=0.0),
        ]
        predictions = self.service._evaluate_chart_predictions(chart_rows)

        self.assertIn("career", predictions)
        self.assertIn("finance", predictions)

        career = predictions["career"]
        self.assertGreater(career["score"], 0.0)
        self.assertGreaterEqual(career["positive_score"], 1.5)
        self.assertGreaterEqual(career["negative_score"], 0.6)
        self.assertEqual("positive", career["effect"])
        self.assertIn("career_growth_strong", career["positive_summary_keys"])
        self.assertIn("bhava_career_reasoning", career["positive_summary_keys"])
        self.assertIn("career_progress_delayed", career["negative_summary_keys"])
        self.assertIn("10th lord", career["summary"].lower())
        self.assertIn("karaka", career["summary"].lower())
        self.assertIn("trace", career)
        self.assertTrue(any("matched" in line.lower() for line in career["trace"]))
        self.assertTrue(any("area framework" in line.lower() for line in career["trace"]))

        finance = predictions["finance"]
        self.assertGreater(finance["score"], 0.0)
        self.assertEqual("positive", finance["effect"])
        self.assertIn("2th lord", finance["summary"].lower())
        self.assertIn("11th lord", finance["summary"].lower())

    def test_rule_repository_persists_optional_result_key(self) -> None:
        rule = Rule(
            condition_json='{"planet": "Moon", "house": 10}',
            result_text="Career growth is strongly indicated.",
            result_key="career_growth_strong",
            category="career",
        )

        rule_id = self.rule_repo.save(rule)
        saved_rules = self.rule_repo.get_all()
        persisted = next(item for item in saved_rules if item.id == rule_id)

        self.assertEqual("career_growth_strong", persisted.result_key)

    def test_build_timeline_events_uses_prediction_summaries(self) -> None:
        scored_predictions = {
            "career": {
                "summary": "Career momentum increases through focused effort.",
                "confidence": "high",
            }
        }

        events = self.service._build_timeline_events("Career opportunity", scored_predictions)

        self.assertEqual(1, len(events))
        self.assertEqual("career", events[0]["type"])
        self.assertEqual("high", events[0]["confidence"])
        self.assertIn("momentum", events[0]["summary"].lower())

    def test_default_gajakesari_yoga_rule_is_seeded_and_matches(self) -> None:
        chart_rows = [
            ChartData(user_id=1, planet_name="Moon", sign="Leo", house=4, degree=12.5),
            ChartData(user_id=1, planet_name="Jupiter", sign="Cancer", house=4, degree=5.0),
            ChartData(user_id=1, planet_name="Venus", sign="Libra", house=7, degree=18.0),
        ]

        predictions = self.service._evaluate_chart_predictions(chart_rows)

        self.assertIn("yoga", predictions)
        yoga = predictions["yoga"]
        self.assertEqual("positive", yoga["effect"])
        self.assertIn("gajakesari_yoga", yoga["positive_summary_keys"])
        self.assertIn("gajakesari", yoga["summary"].lower())

    def test_evaluate_chart_predictions_applies_strength_gate(self) -> None:
        self.rule_repo.save(
            Rule(
                condition_json='{"planet": "Moon", "house": 10}',
                result_text="Career growth is strongly indicated.",
                result_key="career_growth_strong",
                category="career",
                weight=2.3,
                confidence="high",
            )
        )
        weak_strength = {
            "sun": {"planet": "sun", "total": 120.0},
            "moon": {"planet": "moon", "total": 110.0},
        }

        predictions = self.service._evaluate_chart_predictions(
            self.chart_rows,
            shadbala_payload=weak_strength,
        )

        self.assertIn("career", predictions)
        self.assertNotEqual("high", predictions["career"]["confidence"])
        self.assertEqual("downgraded", predictions["career"]["strength_gate"]["status"])

    def test_same_rule_outcome_changes_with_lagna_functional_role(self) -> None:
        self.rule_repo.save(
            Rule(
                condition_json='{"planet": "Mars", "house": 10}',
                result_text="Career rise is strongly indicated.",
                result_key="career_rise_strong",
                category="career",
                weight=2.2,
                confidence="high",
            )
        )
        strong_strength = {
            "sun": {"planet": "sun", "total": 390.0},
            "moon": {"planet": "moon", "total": 360.0},
        }

        aries_chart = [
            ChartData(user_id=1, planet_name="Ascendant", sign="Aries", house=1, degree=0.0),
            ChartData(user_id=1, planet_name="Sun", sign="Leo", house=5, degree=8.0),
            ChartData(user_id=1, planet_name="Mars", sign="Capricorn", house=10, degree=16.5),
        ]
        libra_chart = [
            ChartData(user_id=1, planet_name="Ascendant", sign="Libra", house=1, degree=0.0),
            ChartData(user_id=1, planet_name="Sun", sign="Leo", house=11, degree=8.0),
            ChartData(user_id=1, planet_name="Mars", sign="Capricorn", house=10, degree=16.5),
        ]

        aries_predictions = self.service._evaluate_chart_predictions(
            aries_chart,
            shadbala_payload=strong_strength,
        )
        libra_predictions = self.service._evaluate_chart_predictions(
            libra_chart,
            shadbala_payload=strong_strength,
        )

        self.assertIn("career", aries_predictions)
        self.assertIn("career", libra_predictions)
        self.assertEqual("positive", aries_predictions["career"]["effect"])
        self.assertEqual("negative", libra_predictions["career"]["effect"])
        self.assertGreater(aries_predictions["career"]["score"], 0.0)
        self.assertLess(libra_predictions["career"]["score"], 0.0)
        self.assertIn("functional malefic", libra_predictions["career"]["summary"].lower())
        self.assertTrue(
            any("functional role impact" in line.lower() for line in libra_predictions["career"]["trace"])
        )

    def test_area_framework_predictions_work_without_matching_rules(self) -> None:
        chart_rows = [
            ChartData(user_id=1, planet_name="Ascendant", sign="Aries", house=1, degree=0.0),
            ChartData(user_id=1, planet_name="Sun", sign="Leo", house=5, degree=10.0),
            ChartData(user_id=1, planet_name="Moon", sign="Taurus", house=2, degree=5.0),
            ChartData(user_id=1, planet_name="Saturn", sign="Libra", house=7, degree=15.0),
            ChartData(user_id=1, planet_name="Jupiter", sign="Cancer", house=4, degree=9.0),
            ChartData(user_id=1, planet_name="Venus", sign="Virgo", house=6, degree=10.0),
        ]
        weak_strength = {
            "sun": {"planet": "sun", "total": 120.0},
            "moon": {"planet": "moon", "total": 110.0},
        }

        predictions = self.service._evaluate_chart_predictions(
            chart_rows,
            shadbala_payload=weak_strength,
        )

        self.assertIn("career", predictions)
        self.assertIn("marriage", predictions)
        self.assertIn("finance", predictions)
        self.assertIn("10th lord", predictions["career"]["summary"].lower())
        self.assertIn("karaka condition", predictions["career"]["summary"].lower())
        self.assertIn("strength gate", predictions["career"]["summary"].lower())
        self.assertNotEqual("high", predictions["career"]["confidence"])


if __name__ == "__main__":
    unittest.main()
