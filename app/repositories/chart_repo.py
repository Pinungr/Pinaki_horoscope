import logging
import sqlite3
from typing import List
from app.repositories.database_manager import DatabaseManager
from app.models.domain import ChartData
from app.utils.safe_execution import AppError


logger = logging.getLogger(__name__)

class ChartRepository:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def save_bulk(self, chart_data_list: List[ChartData]) -> None:
        """Saves a list of chart data points (e.g. for a freshly calculated chart)."""
        if not chart_data_list:
            return

        sql = '''
        INSERT INTO chart_data (user_id, planet_name, sign, house, degree, absolute_longitude, is_retrograde)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        '''
        
        # Prepare the dataset as a list of tuples
        values = [(
            data.user_id,
            data.planet_name,
            data.sign,
            data.house,
            data.degree,
            data.absolute_longitude,
            1 if data.is_retrograde else 0
        ) for data in chart_data_list]
        
        try:
            with self.db.connection_context() as conn:
                cursor = conn.cursor()
                cursor.executemany(sql, values)
                conn.commit()
        except sqlite3.Error as exc:
            logger.exception("Failed to save chart data for %d row(s): %s", len(values), exc)
            raise AppError("Unable to save chart data right now. Please try again.") from exc

    def get_by_user_id(self, user_id: int) -> List[ChartData]:
        """Retrieves an entire chart for a specific user."""
        sql = 'SELECT * FROM chart_data WHERE user_id = ?'
        chart_data = []
        try:
            with self.db.connection_context() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (user_id,))
                for row in cursor.fetchall():
                    chart_data.append(ChartData(
                        id=row['id'],
                        user_id=row['user_id'],
                        planet_name=row['planet_name'],
                        sign=row['sign'],
                        house=row['house'],
                        degree=row['degree'],
                        absolute_longitude=float(row['absolute_longitude'] or 0.0),
                        is_retrograde=bool(row['is_retrograde'])
                    ))
            return chart_data
        except sqlite3.Error as exc:
            logger.exception("Failed to load chart data for user %s: %s", user_id, exc)
            raise AppError("Unable to load chart data right now. Please try again.") from exc
    
    def delete_by_user_id(self, user_id: int):
        """Clears chart data for a specific user (useful for recalculations)."""
        sql = 'DELETE FROM chart_data WHERE user_id = ?'
        try:
            with self.db.connection_context() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (user_id,))
                conn.commit()
        except sqlite3.Error as exc:
            logger.exception("Failed to delete chart data for user %s: %s", user_id, exc)
            raise AppError("Unable to remove chart data right now. Please try again.") from exc
