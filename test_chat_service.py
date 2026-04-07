import uuid

from app.models.domain import ChartData, Rule, User
from app.repositories.chart_repo import ChartRepository
from app.repositories.database_manager import DatabaseManager
from app.repositories.rule_repo import RuleRepository
from app.repositories.user_repo import UserRepository
from app.services.horoscope_chat_service import HoroscopeChatService
from app.services.horoscope_service import HoroscopeService


def test_chat_service_local_mode() -> None:
    """Smoke test for local horoscope chat responses."""
    db_path = f"database\\test_chat_service_{uuid.uuid4().hex}.db"
    db_manager = DatabaseManager(db_path)
    db_manager.initialize_schema()

    user_repo = UserRepository(db_manager)
    chart_repo = ChartRepository(db_manager)
    rule_repo = RuleRepository(db_manager)
    horoscope_service = HoroscopeService(db_manager)
    chat_service = HoroscopeChatService(horoscope_service=horoscope_service)

    user_id = user_repo.save(
        User(
            name="Chat User",
            dob="1994-07-28",
            tob="09:15:00",
            place="Kolkata",
            latitude=22.57,
            longitude=88.36,
        )
    )
    chart_repo.save_bulk(
        [
            ChartData(user_id=user_id, planet_name="Moon", sign="Cancer", house=10, degree=12.5),
            ChartData(user_id=user_id, planet_name="Venus", sign="Libra", house=7, degree=18.0),
            ChartData(user_id=user_id, planet_name="Jupiter", sign="Taurus", house=2, degree=5.0),
        ]
    )
    rule_repo.save(
        Rule(
            condition_json='{"planet": "Moon", "house": 10}',
            result_text="Career growth is strongly indicated.",
            category="career",
            priority=1,
            weight=1.3,
            confidence="high",
        )
    )
    rule_repo.save(
        Rule(
            condition_json='{"planet": "Venus", "house": 7}',
            result_text="Marriage opportunities are favorable.",
            category="marriage",
            priority=1,
            weight=0.9,
            confidence="medium",
        )
    )
    rule_repo.save(
        Rule(
            condition_json='{"planet": "Jupiter", "house": 2}',
            result_text="Financial progress improves steadily.",
            category="finance",
            priority=1,
            weight=1.1,
            confidence="high",
        )
    )

    sample_queries = [
        "When will I get a job?",
        "Is marriage good for me?",
        "How is my financial future?",
    ]

    for query in sample_queries:
        result = chat_service.ask(user_id, query)
        print(f"Query: {query}")
        print(f"Intent: {result['intent']}")
        print(f"Source: {result['response_source']}")
        print(f"Response: {result['response']}")
        print("---")
        assert result["response_source"] == "local"
        assert result["response"]

    follow_up_result = chat_service.ask(user_id, "What about that?")
    print(f"Follow-up Intent: {follow_up_result['intent']}")
    print(f"Follow-up Response: {follow_up_result['response']}")
    assert follow_up_result["intent"] == "finance"
    assert "earlier finance question" in follow_up_result["response"].lower()

    extra_queries = [
        "Will I get a promotion?",
        "Is love life supportive?",
        "How are my earnings?",
    ]
    for query in extra_queries:
        chat_service.ask(user_id, query)

    recent_queries = chat_service.get_recent_queries(user_id)
    print(f"Stored Memory Count: {len(recent_queries)}")
    assert len(recent_queries) == 5
    assert recent_queries[-1]["query"] == "How are my earnings?"


if __name__ == "__main__":
    test_chat_service_local_mode()
