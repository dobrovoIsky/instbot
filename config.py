"""Bot configuration."""

import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Limits
MAX_ZIP_SIZE_MB = 100
MAX_ZIP_SIZE_BYTES = MAX_ZIP_SIZE_MB * 1024 * 1024

# Pagination
PAGE_SIZE = 20

# Temp directory for processing ZIPs
TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

# Database
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "bot.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
