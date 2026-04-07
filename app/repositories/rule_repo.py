from typing import List
from app.repositories.database_manager import DatabaseManager
from app.models.domain import Rule

class RuleRepository:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def save(self, rule: Rule) -> int:
        """Saves a new astrology rule to the database."""
        sql = '''
        INSERT INTO rules (condition_json, result_text, priority, category, weight, confidence)
        VALUES (?, ?, ?, ?, ?, ?)
        '''
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (
                rule.condition_json,
                rule.result_text,
                rule.priority,
                rule.category,
                rule.weight,
                rule.confidence
            ))
            conn.commit()
            return cursor.lastrowid

    def get_all(self) -> List[Rule]:
        """Retrieves all rules to be loaded into the Rule Engine."""
        sql = 'SELECT * FROM rules ORDER BY priority DESC'
        rules = []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql)
            for row in cursor.fetchall():
                rules.append(Rule(
                    id=row['id'],
                    condition_json=row['condition_json'],
                    result_text=row['result_text'],
                    priority=row['priority'],
                    category=row['category'],
                    weight=row['weight'],
                    confidence=row['confidence']
                ))
        return rules

    def delete(self, rule_id: int):
        """Deletes a rule."""
        sql = 'DELETE FROM rules WHERE id = ?'
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (rule_id,))
            conn.commit()
