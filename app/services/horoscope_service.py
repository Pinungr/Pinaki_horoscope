from typing import Tuple, List, Dict
from app.repositories.database_manager import DatabaseManager
from app.repositories.user_repo import UserRepository
from app.repositories.chart_repo import ChartRepository
from app.repositories.rule_repo import RuleRepository
from app.engine.calculator import AstrologyEngine
from app.engine.rule_engine import RuleEngine
from app.models.domain import User

class HoroscopeService:
    """Orchestrates astrology logic and database persistence."""
    def __init__(self, db_manager: DatabaseManager):
        self.user_repo = UserRepository(db_manager)
        self.chart_repo = ChartRepository(db_manager)
        self.rule_repo = RuleRepository(db_manager)

    def generate_and_save_chart(self, user_data: dict) -> Tuple[List[Dict], List[str]]:
        """
        Parses user data, computes chart, executes rules, and persists everything.
        Returns display data dictionaries and predictions list.
        """
        try:
            lat = float(user_data.get("latitude", 0.0))
            lon = float(user_data.get("longitude", 0.0))
        except ValueError:
            raise ValueError("Latitude and Longitude must be valid numbers.")

        # Create Domain Model
        user = User(
            name=user_data["name"],
            dob=user_data["dob"],
            tob=user_data["tob"],
            place=user_data["place"],
            latitude=lat,
            longitude=lon
        )

        # Execute Engine
        astrology_engine = AstrologyEngine()
        chart_data_models = astrology_engine.calculate_chart(user)

        # Database Persistence
        # 1. Save User and get ID
        user_id = self.user_repo.save(user)
        
        # 2. Assign User ID to ChartData objects and bulk save
        for cd in chart_data_models:
            cd.user_id = user_id
        self.chart_repo.save_bulk(chart_data_models)

        # Rule Engine Evaluation
        rules = self.rule_repo.get_all()
        predictions = []
        if rules:
            rule_engine = RuleEngine(rules)
            raw_predictions = rule_engine.evaluate(chart_data_models)
            
            # Step 16: Interpret Layer deduplication and scoring
            from app.engine.interpreter import InterpreterEngine
            interpreter = InterpreterEngine()
            predictions = interpreter.interpret(raw_predictions, rules)
            
        if not predictions:
            predictions = [{"text": "Chart generated successfully... No matching rules found.", "category": "System", "score": 0}]

        # Format for UI Response Layer
        display_data = [
            {
                "Planet": cd.planet_name,
                "Sign": cd.sign,
                "House": cd.house,
                "Degree": round(cd.degree, 2)
            }
            for cd in chart_data_models
        ]

        return display_data, predictions

    def get_all_users_dicts(self) -> List[Dict]:
        """Fetches all users and formats them for the UI table."""
        users = self.user_repo.get_all()
        return [
            {
                "id": u.id,
                "name": u.name,
                "dob": u.dob,
                "place": u.place
            } for u in users
        ]

    def delete_user(self, user_id: int):
        self.user_repo.delete(user_id)

    def save_astrology_rule(self, rule_data: dict):
        from app.models.domain import Rule
        r = Rule(
            condition_json=rule_data["condition_json"],
            result_text=rule_data["result_text"],
            priority=rule_data.get("priority", 0),
            category=rule_data.get("category", "")
        )
        self.rule_repo.save(r)

    def load_chart_for_user(self, user_id: int) -> Tuple[List[Dict], List[str]]:
        """Loads a previously calculated chart for a user and re-evaluates rules."""
        chart_data_models = self.chart_repo.get_by_user_id(user_id)
        if not chart_data_models:
            raise ValueError("No chart data found for this user.")

        rules = self.rule_repo.get_all()
        predictions = []
        if rules:
            rule_engine = RuleEngine(rules)
            raw_predictions = rule_engine.evaluate(chart_data_models)
            
            # Step 16: Interpret Layer deduplication and scoring
            from app.engine.interpreter import InterpreterEngine
            interpreter = InterpreterEngine()
            predictions = interpreter.interpret(raw_predictions, rules)
            
        if not predictions:
            predictions = [{"text": "Chart generated successfully... No matching rules found.", "category": "System", "score": 0}]

        display_data = [
            {
                "Planet": cd.planet_name,
                "Sign": cd.sign,
                "House": cd.house,
                "Degree": round(cd.degree, 2)
            }
            for cd in chart_data_models
        ]
        return display_data, predictions
