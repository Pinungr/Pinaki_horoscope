import os
from pathlib import Path
from app.utils.runtime_paths import get_app_root

# Base Directory Setup
BASE_DIR = get_app_root()
CONFIG_DIR = BASE_DIR / "app" / "config"

# Database configuration
DB_DIR = BASE_DIR / "database"
DB_NAME = "horoscope.db"
DB_PATH = DB_DIR / DB_NAME

# Ensure database directory exists upon configuration load
os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)
