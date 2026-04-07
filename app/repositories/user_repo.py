from typing import Optional, List
from app.repositories.database_manager import DatabaseManager
from app.models.domain import User

class UserRepository:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def save(self, user: User) -> int:
        """Saves a user to the database and returns the inserted ID."""
        sql = '''
        INSERT INTO users (name, dob, tob, place, latitude, longitude)
        VALUES (?, ?, ?, ?, ?, ?)
        '''
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (
                user.name, user.dob, user.tob, user.place, user.latitude, user.longitude
            ))
            conn.commit()
            return cursor.lastrowid

    def get_by_id(self, user_id: int) -> Optional[User]:
        """Retrieves a user by ID."""
        sql = 'SELECT * FROM users WHERE id = ?'
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (user_id,))
            row = cursor.fetchone()
            if row:
                return User(
                    id=row['id'],
                    name=row['name'],
                    dob=row['dob'],
                    tob=row['tob'],
                    place=row['place'],
                    latitude=row['latitude'],
                    longitude=row['longitude']
                )
        return None

    def get_all(self) -> List[User]:
        """Retrieves all users."""
        sql = 'SELECT * FROM users'
        users = []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql)
            for row in cursor.fetchall():
                users.append(User(
                    id=row['id'],
                    name=row['name'],
                    dob=row['dob'],
                    tob=row['tob'],
                    place=row['place'],
                    latitude=row['latitude'],
                    longitude=row['longitude']
                ))
        return users

    def delete(self, user_id: int):
        """Deletes a user by ID."""
        sql = 'DELETE FROM users WHERE id = ?'
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (user_id,))
            conn.commit()
