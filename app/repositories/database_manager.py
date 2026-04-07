import sqlite3
import logging
import json
from pathlib import Path
from app.config.settings import DB_PATH
from app.utils.safe_execution import AppError
from app.utils.runtime_paths import resolve_resource

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages SQLite database connections and schema initialization."""
    
    def __init__(self, db_path: str = str(DB_PATH)):
        self.db_path = db_path

    def get_connection(self):
        """Returns a new SQLite database connection."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Access columns by name
            return conn
        except sqlite3.Error as exc:
            logger.exception("Failed to open database connection '%s': %s", self.db_path, exc)
            raise AppError("Unable to connect to the local database right now. Please try again.") from exc

    def _migrate_rules_table(self, conn: sqlite3.Connection) -> None:
        """Safely extends the existing rules table with scoring columns."""
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(rules)")
        existing_columns = {row["name"] for row in cursor.fetchall()}

        alter_statements = []
        if "effect" not in existing_columns:
            alter_statements.append("ALTER TABLE rules ADD COLUMN effect TEXT DEFAULT 'positive'")
        if "weight" not in existing_columns:
            alter_statements.append("ALTER TABLE rules ADD COLUMN weight REAL DEFAULT 1.0")
        if "confidence" not in existing_columns:
            alter_statements.append("ALTER TABLE rules ADD COLUMN confidence TEXT DEFAULT 'medium'")

        for statement in alter_statements:
            cursor.execute(statement)

        if alter_statements:
            logger.info("Applied rules table migration for scoring/effect columns.")

    def _migrate_users_table(self, conn: sqlite3.Connection) -> None:
        """Safely extends the users table with structured location columns."""
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(users)")
        existing_columns = {row["name"] for row in cursor.fetchall()}

        alter_statements = []
        if "state" not in existing_columns:
            alter_statements.append("ALTER TABLE users ADD COLUMN state TEXT")
        if "city" not in existing_columns:
            alter_statements.append("ALTER TABLE users ADD COLUMN city TEXT")

        for statement in alter_statements:
            cursor.execute(statement)

        if alter_statements:
            logger.info("Applied users table migration for location columns.")

    def _seed_locations_table(self, conn: sqlite3.Connection) -> None:
        """Loads bundled India state/city coordinates into the locations table if empty."""
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM locations")
        if cursor.fetchone()[0] > 0:
            return

        data_file = resolve_resource("app", "data", "india_locations.json")
        if not data_file.exists():
            logger.warning("Location seed file not found at %s", data_file)
            return

        raw_payload = data_file.read_text(encoding="utf-8").strip()
        try:
            payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            payload = json.loads(raw_payload.rstrip(", \r\n\t"))

        if isinstance(payload, list):
            payload = next(
                (
                    item for item in payload
                    if isinstance(item, dict) and str(item.get("name", "")).strip().lower() == "india"
                ),
                payload[0] if payload else {},
            )

        location_rows = []
        for state in payload.get("states", []):
            state_name = str(state.get("name", "")).strip()
            timezone = str(state.get("timezone", "Asia/Kolkata") or "Asia/Kolkata").strip()
            for city in state.get("cities", []):
                city_name = str(city.get("name", "")).strip()
                latitude = city.get("latitude")
                longitude = city.get("longitude")
                if not state_name or not city_name or latitude is None or longitude is None:
                    continue

                try:
                    location_rows.append(
                        (
                            "India",
                            state_name,
                            city_name,
                            float(latitude),
                            float(longitude),
                            str(city.get("timezone", timezone) or timezone).strip(),
                        )
                    )
                except (TypeError, ValueError):
                    continue

        if not location_rows:
            logger.warning("No valid location rows were found in %s", data_file)
            return

        cursor.executemany(
            """
            INSERT OR IGNORE INTO locations (country, state, city, latitude, longitude, timezone)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            location_rows,
        )
        logger.info("Seeded %d location rows into the locations table.", len(location_rows))

    def initialize_schema(self):
        """Creates the initial database schema and applies safe migrations."""
        schema = '''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            dob TEXT NOT NULL,
            tob TEXT NOT NULL,
            place TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            state TEXT,
            city TEXT
        );
        
        CREATE TABLE IF NOT EXISTS planets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );
        
        CREATE TABLE IF NOT EXISTS chart_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            planet_name TEXT NOT NULL,
            sign TEXT NOT NULL,
            house INTEGER NOT NULL,
            degree REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            condition_json TEXT NOT NULL,
            result_text TEXT NOT NULL,
            priority INTEGER DEFAULT 0,
            category TEXT,
            effect TEXT DEFAULT 'positive',
            weight REAL DEFAULT 1.0,
            confidence TEXT DEFAULT 'medium'
        );

        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country TEXT NOT NULL DEFAULT 'India',
            state TEXT NOT NULL,
            city TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            timezone TEXT DEFAULT 'Asia/Kolkata',
            UNIQUE(state, city)
        );
        '''
        
        try:
            with self.get_connection() as conn:
                # Execution of the schema script
                conn.executescript(schema)
                self._migrate_rules_table(conn)
                self._migrate_users_table(conn)
                self._seed_locations_table(conn)
                
                # We optionally pre-populate the planets table if it's empty
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM planets')
                if cursor.fetchone()[0] == 0:
                    planets = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu", "Ascendant"]
                    cursor.executemany('INSERT INTO planets (name) VALUES (?)', [(p,) for p in planets])
                
                # Pre-populate some default astrology rules if empty
                cursor.execute('SELECT COUNT(*) FROM rules')
                if cursor.fetchone()[0] == 0:
                    default_rules = [
                        ('{"planet": "Sun", "house": 1}', "Sun in the 1st House provides strong vitality, leadership skills, and radiant energy.", 10, "General"),
                        ('{"planet": "Moon", "sign": "Cancer"}', "Moon in Cancer (Own Sign) gives deep emotional intelligence and strong intuition.", 15, "Strength"),
                        ('{"AND": [{"planet": "Sun", "house": 1}, {"planet": "Mercury", "house": 1}]}', "Budhaditya Yoga in 1st House: Displays high intelligence, charismatic speech, and strong character.", 50, "Yoga"),
                        ('{"planet": "Jupiter", "house": 1}', "Jupiter in the 1st House grants wisdom, optimism, and a protective aura.", 10, "General")
                    ]
                    cursor.executemany('INSERT INTO rules (condition_json, result_text, priority, category) VALUES (?, ?, ?, ?)', default_rules)

                conn.commit()
                logger.debug("Database schema initialized successfully.")
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")
            raise AppError("Unable to initialize the local database. Please restart the application.") from e
