import os
from pathlib import Path

# Base Directory Setup
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Database configuration
DB_DIR = BASE_DIR / "database"
DB_NAME = "horoscope.db"
DB_PATH = DB_DIR / DB_NAME

# Ensure database directory exists upon configuration load
os.makedirs(DB_DIR, exist_ok=True)
