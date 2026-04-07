import os
import uuid

from app.models.domain import Rule
from app.repositories.database_manager import DatabaseManager
from app.repositories.rule_repo import RuleRepository
from app.services.horoscope_service import HoroscopeService


def test_prediction_scoring() -> None:
    """Validates category scoring and confidence output for prediction summaries."""
    db_path = f"database\\test_prediction_scoring_{uuid.uuid4().hex}.db"

    try:
        db_manager = DatabaseManager(db_path)
        db_manager.initialize_schema()

        rule_repo = RuleRepository(db_manager)
        service = HoroscopeService(db_manager)

        sample_rules = [
            Rule(
                condition_json='{"planet": "Saturn", "house": 10}',
                result_text="Career growth will be slow but stable.",
                category="career",
                priority=1,
                weight=0.8,
                confidence="high",
            ),
            Rule(
                condition_json='{"planet": "Sun", "house": 10}',
                result_text="Career progress improves through discipline and patience.",
                category="career",
                priority=1,
                weight=0.7,
                confidence="medium",
            ),
            Rule(
                condition_json='{"planet": "Mars", "house": 10}',
                result_text="Career growth may be delayed but remain stable.",
                category="career",
                priority=1,
                weight=0.9,
                confidence="high",
            ),
            Rule(
                condition_json='{"planet": "Venus", "house": 7}',
                result_text="Marriage matters require patience.",
                category="marriage",
                priority=1,
                weight=0.6,
                confidence="medium",
            ),
        ]

        for rule in sample_rules:
            rule_repo.save(rule)

        rules = service.rule_repo.get_all()
        raw_predictions = [rule.result_text for rule in sample_rules]
        scored_predictions = service._score_rule_engine_output(raw_predictions, rules)

        print("Scored Predictions:")
        print(scored_predictions)

        career = scored_predictions["career"]
        marriage = scored_predictions["marriage"]

        assert career["score"] == 2.4, "Career score should be 2.4"
        assert career["confidence"] == "high", "Career confidence should be high"
        assert "stable" in career["summary"].lower(), "Career summary should mention stability"

        assert marriage["score"] == 0.6, "Marriage score should be 0.6"
        assert marriage["confidence"] in {"low", "medium"}, "Marriage confidence should be low or medium"
        assert "marriage" in marriage["summary"].lower(), "Marriage summary should mention marriage"

        print("Prediction scoring test passed.")
    finally:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except PermissionError:
                pass


if __name__ == "__main__":
    test_prediction_scoring()
