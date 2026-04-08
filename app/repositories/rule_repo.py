import logging
import sqlite3
from typing import List
from app.repositories.database_manager import DatabaseManager
from app.models.domain import Rule
from app.utils.safe_execution import AppError


logger = logging.getLogger(__name__)

class RuleRepository:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def save(self, rule: Rule) -> int:
        """Saves a new astrology rule to the database."""
        sql = '''
        INSERT INTO rules (condition_json, result_text, result_key, priority, category, effect, weight, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        '''
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (
                    rule.condition_json,
                    rule.result_text,
                    rule.result_key,
                    rule.priority,
                    rule.category,
                    rule.effect,
                    rule.weight,
                    rule.confidence
                ))
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error as exc:
            logger.exception("Failed to save astrology rule: %s", exc)
            raise AppError("Unable to save the rule right now. Please try again.") from exc

    def get_all(self) -> List[Rule]:
        """Retrieves all rules to be loaded into the Rule Engine."""
        sql = 'SELECT * FROM rules ORDER BY priority DESC'
        rules = []
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                for row in cursor.fetchall():
                    rules.append(Rule(
                        id=row['id'],
                        condition_json=row['condition_json'],
                        result_text=row['result_text'],
                        result_key=row["result_key"] if "result_key" in row.keys() else None,
                        priority=row['priority'],
                        category=row['category'],
                        effect=row["effect"] if "effect" in row.keys() else "positive",
                        weight=row['weight'],
                        confidence=row['confidence']
                    ))
            return rules
        except sqlite3.Error as exc:
            logger.exception("Failed to load astrology rules: %s", exc)
            raise AppError("Unable to load astrology rules right now. Please try again.") from exc

    def delete(self, rule_id: int):
        """Deletes a rule."""
        sql = 'DELETE FROM rules WHERE id = ?'
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (rule_id,))
                conn.commit()
        except sqlite3.Error as exc:
            logger.exception("Failed to delete rule %s: %s", rule_id, exc)
            raise AppError("Unable to delete the rule right now. Please try again.") from exc
