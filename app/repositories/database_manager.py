import sqlite3
import logging
from app.config.settings import DB_PATH

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages SQLite database connections and schema initialization."""
    
    def __init__(self, db_path: str = str(DB_PATH)):
        self.db_path = db_path

    def get_connection(self):
        """Returns a new SQLite database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Access columns by name
        return conn

    def _migrate_rules_table(self, conn: sqlite3.Connection) -> None:
        """Safely extends the existing rules table with scoring columns."""
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(rules)")
        existing_columns = {row["name"] for row in cursor.fetchall()}

        alter_statements = []
        if "weight" not in existing_columns:
            alter_statements.append("ALTER TABLE rules ADD COLUMN weight REAL DEFAULT 1.0")
        if "confidence" not in existing_columns:
            alter_statements.append("ALTER TABLE rules ADD COLUMN confidence TEXT DEFAULT 'medium'")

        for statement in alter_statements:
            cursor.execute(statement)

        if alter_statements:
            logger.info("Applied rules table migration for scoring columns.")

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
            longitude REAL
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
            weight REAL DEFAULT 1.0,
            confidence TEXT DEFAULT 'medium'
        );
        '''
        
        try:
            with self.get_connection() as conn:
                # Execution of the schema script
                conn.executescript(schema)
                self._migrate_rules_table(conn)
                
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
            raise
