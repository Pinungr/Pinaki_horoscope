from typing import List
from app.repositories.database_manager import DatabaseManager
from app.models.domain import ChartData

class ChartRepository:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def save_bulk(self, chart_data_list: List[ChartData]) -> None:
        """Saves a list of chart data points (e.g. for a freshly calculated chart)."""
        if not chart_data_list:
            return

        sql = '''
        INSERT INTO chart_data (user_id, planet_name, sign, house, degree)
        VALUES (?, ?, ?, ?, ?)
        '''
        
        # Prepare the dataset as a list of tuples
        values = [(
            data.user_id,
            data.planet_name,
            data.sign,
            data.house,
            data.degree
        ) for data in chart_data_list]
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(sql, values)
            conn.commit()

    def get_by_user_id(self, user_id: int) -> List[ChartData]:
        """Retrieves an entire chart for a specific user."""
        sql = 'SELECT * FROM chart_data WHERE user_id = ?'
        chart_data = []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (user_id,))
            for row in cursor.fetchall():
                chart_data.append(ChartData(
                    id=row['id'],
                    user_id=row['user_id'],
                    planet_name=row['planet_name'],
                    sign=row['sign'],
                    house=row['house'],
                    degree=row['degree']
                ))
        return chart_data
    
    def delete_by_user_id(self, user_id: int):
        """Clears chart data for a specific user (useful for recalculations)."""
        sql = 'DELETE FROM chart_data WHERE user_id = ?'
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (user_id,))
            conn.commit()
