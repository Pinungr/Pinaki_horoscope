import logging
import sqlite3
from typing import List, Optional, Dict

from app.repositories.database_manager import DatabaseManager
from app.utils.safe_execution import AppError


logger = logging.getLogger(__name__)


class LocationRepository:
    """Provides state/city lookup data backed by the local locations table."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def get_states(self) -> List[str]:
        """Returns all available states ordered alphabetically."""
        sql = "SELECT DISTINCT state FROM locations ORDER BY state"
        try:
            with self.db.connection_context() as conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                return [row["state"] for row in cursor.fetchall() if row["state"]]
        except sqlite3.Error as exc:
            logger.exception("Failed to load states from locations table: %s", exc)
            raise AppError("Unable to load location states right now. Please try again.") from exc

    def get_cities_by_state(self, state: str) -> List[str]:
        """Returns all cities for a given state ordered alphabetically."""
        sql = "SELECT city FROM locations WHERE state = ? ORDER BY city"
        try:
            with self.db.connection_context() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (state,))
                return [row["city"] for row in cursor.fetchall() if row["city"]]
        except sqlite3.Error as exc:
            logger.exception("Failed to load cities for state '%s': %s", state, exc)
            raise AppError("Unable to load cities right now. Please try again.") from exc

    def get_location(self, state: str, city: str) -> Optional[Dict[str, object]]:
        """Returns location details for a state/city pair."""
        sql = """
        SELECT state, city, latitude, longitude, timezone
        FROM locations
        WHERE state = ? AND city = ?
        """
        try:
            with self.db.connection_context() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (state, city))
                row = cursor.fetchone()
                if not row:
                    return None

                return {
                    "state": row["state"],
                    "city": row["city"],
                    "latitude": row["latitude"],
                    "longitude": row["longitude"],
                    "timezone": row["timezone"],
                }
        except sqlite3.Error as exc:
            logger.exception("Failed to load location details for %s, %s: %s", city, state, exc)
            raise AppError("Unable to load location details right now. Please try again.") from exc
