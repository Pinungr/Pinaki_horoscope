import sqlite3
import logging
import json
import queue
import threading
from pathlib import Path
from contextlib import contextmanager
from app.config.settings import DB_PATH
from app.utils.safe_execution import AppError
from app.utils.runtime_paths import resolve_resource

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages SQLite database connections with thread-safe pooling."""
    
    def __init__(self, db_path: str = str(DB_PATH), pool_size: int = 5):
        self.db_path = db_path
        self.pool_size = pool_size
        self._pool = queue.Queue()
        self._lock = threading.Lock()
        self._created_connections = 0

    def get_connection(self):
        """
        Retrieves a connection from the pool or creates a new one.
        Note: Use connection_context() instead for automatic cleanup.
        """
        try:
            return self._pool.get(block=False)
        except queue.Empty:
            with self._lock:
                if self._created_connections < self.pool_size:
                    conn = self._create_new_connection()
                    self._created_connections += 1
                    return conn
            # If pool is full and empty, block until one is available
            return self._pool.get(block=True)

    def _create_new_connection(self):
        """Creates a raw SQLite connection with standard configuration."""
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrency in desktop environments
            conn.execute("PRAGMA journal_mode=WAL")
            return conn
        except sqlite3.Error as exc:
            logger.exception("Failed to open database connection '%s': %s", self.db_path, exc)
            raise AppError("Unable to connect to the local database. Please try again.") from exc

    def return_connection(self, conn: sqlite3.Connection):
        """Returns a connection to the pool."""
        try:
            # Ensure no pending transactions before returning
            if conn.in_transaction:
                conn.rollback()
            self._pool.put(conn)
        except Exception as exc:
            logger.error("Error returning connection to pool: %s", exc)
            try:
                conn.close()
            except:
                pass

    @contextmanager
    def connection_context(self):
        """
        Context manager to lease and return database connections safely.
        Usage: with db_manager.connection_context() as conn: ...
        """
        conn = self.get_connection()
        try:
            yield conn
        finally:
            self.return_connection(conn)

    def _migrate_chart_data_table(self, conn: sqlite3.Connection) -> None:
        """Safely extends the existing chart_data table with exact astronomical coordinates."""
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(chart_data)")
        existing_columns = {row["name"] for row in cursor.fetchall()}

        alter_statements = []
        if "absolute_longitude" not in existing_columns:
            alter_statements.append("ALTER TABLE chart_data ADD COLUMN absolute_longitude REAL DEFAULT 0.0")
        if "is_retrograde" not in existing_columns:
            alter_statements.append("ALTER TABLE chart_data ADD COLUMN is_retrograde INTEGER DEFAULT 0")

        for statement in alter_statements:
            cursor.execute(statement)

        if alter_statements:
            logger.info("Applied chart_data table migration for precision astronomy columns.")

    def _migrate_rules_table(self, conn: sqlite3.Connection) -> None:
        """Safely extends the existing rules table with scoring columns."""
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(rules)")
        existing_columns = {row["name"] for row in cursor.fetchall()}

        alter_statements = []
        if "priority" not in existing_columns:
            alter_statements.append("ALTER TABLE rules ADD COLUMN priority INTEGER DEFAULT 0")
        if "category" not in existing_columns:
            alter_statements.append("ALTER TABLE rules ADD COLUMN category TEXT")
        if "effect" not in existing_columns:
            alter_statements.append("ALTER TABLE rules ADD COLUMN effect TEXT DEFAULT 'positive'")
        if "weight" not in existing_columns:
            alter_statements.append("ALTER TABLE rules ADD COLUMN weight REAL DEFAULT 1.0")
        if "confidence" not in existing_columns:
            alter_statements.append("ALTER TABLE rules ADD COLUMN confidence TEXT DEFAULT 'medium'")
        if "result_key" not in existing_columns:
            alter_statements.append("ALTER TABLE rules ADD COLUMN result_key TEXT")

        for statement in alter_statements:
            conn.execute(statement)

        key_backfills = {
            "Sun in the 1st House provides strong vitality, leadership skills, and radiant energy.": "sun_first_house_vitality",
            "Moon in Cancer (Own Sign) gives deep emotional intelligence and strong intuition.": "moon_cancer_intuition",
            "Budhaditya Yoga in 1st House: Displays high intelligence, charismatic speech, and strong character.": "budhaditya_yoga_first_house",
            "Jupiter in the 1st House grants wisdom, optimism, and a protective aura.": "jupiter_first_house_wisdom",
            "Gajakesari Yoga is present: Moon and Jupiter combine in a kendra, supporting wisdom, recognition, and emotional strength.": "gajakesari_yoga",
        }
        for result_text, result_key in key_backfills.items():
            cursor.execute(
                """
                UPDATE rules
                SET result_key = ?
                WHERE result_text = ? AND (result_key IS NULL OR TRIM(result_key) = '')
                """,
                (result_key, result_text),
            )

        # Ticket P0.3: Data cleanup migrations
        # 1. Rename 'sasa_yoga' to 'shasha_yoga' to match canonical ID
        cursor.execute("UPDATE rules SET result_key = 'shasha_yoga' WHERE result_key = 'sasa_yoga'")
        # 2. Fix 'Libre' typo in condition_json for Malavya Yoga
        cursor.execute(
            """
            UPDATE rules 
            SET condition_json = REPLACE(condition_json, '"sign": "Libre"', '"sign": "Libra"')
            WHERE result_key = 'malavya_yoga' AND condition_json LIKE '%"sign": "Libre"%'
            """
        )

        if alter_statements or cursor.rowcount > 0:
            logger.info("Applied rules table migrations and data cleanup.")

    def _seed_default_rules(self, conn: sqlite3.Connection) -> None:
        """Ensures core bundled rules exist without creating duplicates."""
        default_rules = [
            (
                '{"planet": "Sun", "house": 1}',
                "Sun in the 1st House provides strong vitality, leadership skills, and radiant energy.",
                "sun_first_house_vitality",
                10,
                "General",
            ),
            (
                '{"planet": "Moon", "sign": "Cancer"}',
                "Moon in Cancer (Own Sign) gives deep emotional intelligence and strong intuition.",
                "moon_cancer_intuition",
                15,
                "Strength",
            ),
            (
                '{"AND": [{"planet": "Sun", "house": 1}, {"planet": "Mercury", "house": 1}]}',
                "Budhaditya Yoga in 1st House: Displays high intelligence, charismatic speech, and strong character.",
                "budhaditya_yoga_first_house",
                50,
                "Yoga",
            ),
            (
                '{"planet": "Jupiter", "house": 1}',
                "Jupiter in the 1st House grants wisdom, optimism, and a protective aura.",
                "jupiter_first_house_wisdom",
                10,
                "General",
            ),
            (
                '{"AND": [{"type": "conjunction", "planets": ["Moon", "Jupiter"]}, {"type": "in_kendra", "planet": "Jupiter"}]}',
                "Gajakesari Yoga is present: Moon and Jupiter combine in a kendra, supporting wisdom, recognition, and emotional strength.",
                "gajakesari_yoga",
                60,
                "Yoga",
            ),
            (
                '{"AND": [{"planet": "Mars", "type": "in_kendra"}, {"OR": [{"planet": "Mars", "sign": "Aries"}, {"planet": "Mars", "sign": "Scorpio"}, {"planet": "Mars", "sign": "Capricorn"}]}]}',
                "Ruchaka Yoga: Mars is powerful in a Kendra. Grants courage, leadership, and physical power.",
                "ruchaka_yoga",
                70,
                "Yoga",
            ),
            (
                '{"AND": [{"planet": "Mercury", "type": "in_kendra"}, {"OR": [{"planet": "Mercury", "sign": "Gemini"}, {"planet": "Mercury", "sign": "Virgo"}]}]}',
                "Bhadra Yoga: Mercury is powerful in a Kendra. Grants intellectual brilliance and eloquent speech.",
                "bhadra_yoga",
                70,
                "Yoga",
            ),
            (
                '{"AND": [{"planet": "Jupiter", "type": "in_kendra"}, {"OR": [{"planet": "Jupiter", "sign": "Sagittarius"}, {"planet": "Jupiter", "sign": "Pisces"}, {"planet": "Jupiter", "sign": "Cancer"}]}]}',
                "Hamsa Yoga: Jupiter is powerful in a Kendra. Grants wisdom, spirituality, and divine grace.",
                "hamsa_yoga",
                70,
                "Yoga",
            ),
            (
                '{"AND": [{"planet": "Venus", "type": "in_kendra"}, {"OR": [{"planet": "Venus", "sign": "Taurus"}, {"planet": "Venus", "sign": "Libra"}, {"planet": "Venus", "sign": "Pisces"}]}]}',
                "Malavya Yoga: Venus is powerful in a Kendra. Grants prosperity, luxury, and artistic talent.",
                "malavya_yoga",
                70,
                "Yoga",
            ),
            (
                '{"AND": [{"planet": "Saturn", "type": "in_kendra"}, {"OR": [{"planet": "Saturn", "sign": "Capricorn"}, {"planet": "Saturn", "sign": "Aquarius"}, {"planet": "Saturn", "sign": "Libra"}]}]}',
                "Shasha Yoga: Saturn is powerful in a Kendra. Grants persistence, authority, and mass leadership.",
                "shasha_yoga",
                70,
                "Yoga",
            ),
            (
                '{"AND": [{"planet": "Jupiter", "house": 10}, {"OR": [{"planet": "Moon", "house": 1}, {"planet": "lagna", "house": 1}]}]}',
                "Amala Yoga: A strong benefic in the 10th house. Promises spotless reputation and professional success.",
                "amala_yoga",
                65,
                "Yoga",
            ),
        ]

        cursor = conn.cursor()
        for condition_json, result_text, result_key, priority, category in default_rules:
            # Check if rule exists by result_key
            cursor.execute("SELECT id, condition_json, result_text FROM rules WHERE result_key = ?", (result_key,))
            existing = cursor.fetchone()

            if existing:
                # If it exists, update it to ensure typo fixes and content updates are applied
                if existing["condition_json"] != condition_json or existing["result_text"] != result_text:
                    cursor.execute(
                        """
                        UPDATE rules 
                        SET condition_json = ?, result_text = ?, priority = ?, category = ?
                        WHERE id = ?
                        """,
                        (condition_json, result_text, priority, category, existing["id"]),
                    )
            else:
                # If not exists, insert but still double check by content as fallback
                cursor.execute(
                    "SELECT 1 FROM rules WHERE condition_json = ? AND result_text = ?",
                    (condition_json, result_text),
                )
                if not cursor.fetchone():
                    cursor.execute(
                        """
                        INSERT INTO rules (condition_json, result_text, result_key, priority, category)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (condition_json, result_text, result_key, priority, category),
                    )

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
            absolute_longitude REAL DEFAULT 0.0,
            is_retrograde INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        
        CREATE TABLE IF NOT EXISTS rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            condition_json TEXT NOT NULL,
            result_text TEXT NOT NULL,
            result_key TEXT,
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
            with self.connection_context() as conn:
                # Execution of the schema script
                conn.executescript(schema)
                self._migrate_chart_data_table(conn)
                self._migrate_rules_table(conn)
                self._migrate_users_table(conn)
                self._seed_locations_table(conn)
                
                # We optionally pre-populate the planets table if it's empty
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM planets')
                if cursor.fetchone()[0] == 0:
                    planets = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu", "Ascendant"]
                    cursor.executemany('INSERT INTO planets (name) VALUES (?)', [(p,) for p in planets])
                self._seed_default_rules(conn)

                conn.commit()
                logger.debug("Database schema initialized successfully.")
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")
            raise AppError("Unable to initialize the local database. Please restart the application.") from e
