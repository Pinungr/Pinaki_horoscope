import logging
import sqlite3
from typing import Optional, List
from app.repositories.database_manager import DatabaseManager
from app.models.domain import User
from app.utils.validators import validate_date, validate_time, validate_lat_long
from app.utils.safe_execution import AppError


logger = logging.getLogger(__name__)

class UserRepository:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    @staticmethod
    def _row_value(row, key: str):
        """Reads an optional sqlite Row field while staying compatible with older schemas."""
        return row[key] if key in row.keys() else None

    def save(self, user: User) -> int:
        """Saves a user to the database and returns the inserted ID."""
        if user is None:
            raise ValueError("User is required for persistence.")

        name = str(user.name or "").strip()
        if not name:
            raise ValueError("Name is required.")

        place = str(user.place or "").strip()
        if not place:
            raise ValueError("Place is required.")

        dob = validate_date(user.dob)
        tob = validate_time(user.tob)
        latitude, longitude = validate_lat_long(user.latitude, user.longitude)

        sql = '''
        INSERT INTO users (name, dob, tob, place, latitude, longitude, state, city)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        '''
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (
                    name,
                    dob,
                    tob,
                    place,
                    latitude,
                    longitude,
                    str(user.state).strip() if user.state is not None and str(user.state).strip() else None,
                    str(user.city).strip() if user.city is not None and str(user.city).strip() else None,
                ))
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error as exc:
            logger.exception("Failed to save user '%s': %s", name, exc)
            raise AppError("Unable to save the user right now. Please try again.") from exc

    def get_by_id(self, user_id: int) -> Optional[User]:
        """Retrieves a user by ID."""
        sql = 'SELECT * FROM users WHERE id = ?'
        try:
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
                        longitude=row['longitude'],
                        state=self._row_value(row, "state"),
                        city=self._row_value(row, "city"),
                    )
            return None
        except sqlite3.Error as exc:
            logger.exception("Failed to load user %s: %s", user_id, exc)
            raise AppError("Unable to load the selected user right now. Please try again.") from exc

    def get_all(self) -> List[User]:
        """Retrieves all users."""
        sql = 'SELECT * FROM users'
        users = []
        try:
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
                        longitude=row['longitude'],
                        state=self._row_value(row, "state"),
                        city=self._row_value(row, "city"),
                    ))
            return users
        except sqlite3.Error as exc:
            logger.exception("Failed to load user list: %s", exc)
            raise AppError("Unable to load saved users right now. Please try again.") from exc

    def delete(self, user_id: int):
        """Deletes a user by ID."""
        sql = 'DELETE FROM users WHERE id = ?'
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (user_id,))
                conn.commit()
        except sqlite3.Error as exc:
            logger.exception("Failed to delete user %s: %s", user_id, exc)
            raise AppError("Unable to delete the user right now. Please try again.") from exc
