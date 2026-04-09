import unittest
import os
import sqlite3
from app.repositories.database_manager import DatabaseManager
from tests.test_support import build_temp_db_path, cleanup_temp_db

class DatabaseSeedingTests(unittest.TestCase):
    def setUp(self):
        self.db_path = build_temp_db_path("test_seeding")
        self.db_manager = DatabaseManager(self.db_path)

    def tearDown(self):
        cleanup_temp_db(self.db_path)

    def test_initialization_seeds_expected_yogas(self):
        self.db_manager.initialize_schema()
        
        with self.db_manager.connection_context() as conn:
            cursor = conn.cursor()
            
            # Verify Shasha Yoga (Canonical Key)
            cursor.execute("SELECT condition_json FROM rules WHERE result_key = 'shasha_yoga'")
            shasha = cursor.fetchone()
            self.assertIsNotNone(shasha, "shasha_yoga should be seeded")
            
            # Verify Malavya Yoga (No 'Libre' typo)
            cursor.execute("SELECT condition_json FROM rules WHERE result_key = 'malavya_yoga'")
            malavya = cursor.fetchone()
            self.assertIsNotNone(malavya, "malavya_yoga should be seeded")
            self.assertIn('"sign": "Libra"', malavya["condition_json"])
            self.assertNotIn('"sign": "Libre"', malavya["condition_json"])

    def test_seeding_is_idempotent(self):
        self.db_manager.initialize_schema()
        
        with self.db_manager.connection_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM rules")
            initial_count = cursor.fetchone()[0]
            
            # Run initialization again
            self.db_manager.initialize_schema()
            
            cursor.execute("SELECT COUNT(*) FROM rules")
            new_count = cursor.fetchone()[0]
            
            self.assertEqual(initial_count, new_count, "Repeated initialization should not add duplicate rules")

    def test_migration_fixes_legacy_data(self):
        # 1. Manually create a dirty legacy DB
        conn = sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE rules (id INTEGER PRIMARY KEY, condition_json TEXT, result_text TEXT, result_key TEXT)")
        # Insert legacy 'sasa_yoga'
        conn.execute(
            "INSERT INTO rules (condition_json, result_text, result_key) VALUES (?, ?, ?)",
            ('{"planet": "Saturn"}', "Old Sasa", "sasa_yoga")
        )
        # Insert legacy Malavya with typo
        conn.execute(
            "INSERT INTO rules (condition_json, result_text, result_key) VALUES (?, ?, ?)",
            ('{"planet": "Venus", "sign": "Libre"}', "Old Malavya", "malavya_yoga")
        )
        conn.commit()
        conn.close()
        
        # 2. Run initialization (which triggers migrations)
        self.db_manager.initialize_schema()
        
        # 3. Verify fixes
        with self.db_manager.connection_context() as conn:
            cursor = conn.cursor()
            
            # Sasa -> Shasha
            cursor.execute("SELECT 1 FROM rules WHERE result_key = 'sasa_yoga'")
            self.assertIsNone(cursor.fetchone(), "sasa_yoga should have been migrated")
            
            cursor.execute("SELECT 1 FROM rules WHERE result_key = 'shasha_yoga'")
            self.assertIsNotNone(cursor.fetchone(), "shasha_yoga should now exist")
            
            # Libre -> Libra
            cursor.execute("SELECT condition_json FROM rules WHERE result_key = 'malavya_yoga'")
            row = cursor.fetchone()
            self.assertIn('"sign": "Libra"', row["condition_json"])
            self.assertNotIn('"sign": "Libre"', row["condition_json"])

if __name__ == "__main__":
    unittest.main()
