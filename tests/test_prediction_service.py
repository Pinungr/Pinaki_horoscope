from __future__ import annotations

import unittest

from tests.test_support import build_temp_db_path, cleanup_temp_db, install_engine_dependency_stubs

install_engine_dependency_stubs()

from app.models.domain import ChartData, Rule
from app.repositories.database_manager import DatabaseManager
from app.repositories.rule_repo import RuleRepository
from app.services.horoscope_service import HoroscopeService


class HoroscopePredictionServiceTests(unittest.TestCase):
    def setUp(self) -> None:
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
        cleanup_temp_db(self.db_path)

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

        predictions = self.service._evaluate_chart_predictions(self.chart_rows)

        self.assertIn("career", predictions)
        self.assertIn("finance", predictions)

        career = predictions["career"]
        self.assertEqual(0.9, career["score"])
        self.assertEqual(1.5, career["positive_score"])
        self.assertEqual(0.6, career["negative_score"])
        self.assertEqual("positive", career["effect"])
        self.assertEqual(["career_growth_strong"], career["positive_summary_keys"])
        self.assertEqual(["career_progress_delayed"], career["negative_summary_keys"])
        self.assertIn("however", career["summary"].lower())
        self.assertIn("trace", career)
        self.assertTrue(any("matched" in line.lower() for line in career["trace"]))

        finance = predictions["finance"]
        self.assertEqual(1.1, finance["score"])
        self.assertEqual("positive", finance["effect"])
        self.assertIn("financial", finance["summary"].lower())

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


if __name__ == "__main__":
    unittest.main()
