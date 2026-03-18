"""
Dashboard configuration
"""

from pathlib import Path

# Database
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "invest.db"

# Refresh settings (seconds)
REFRESH_INTERVAL = 10

# Default UI settings
DEFAULT_MAX_ROWS = 25
DEFAULT_MIN_CONFIDENCE = 1

# Layout
PAGE_TITLE = "Trading Signals Dashboard"
PAGE_ICON = "📈"

# Feature flags
ENABLE_AUTO_REFRESH = True
ENABLE_SIGNAL_CARDS = True
ENABLE_TABLE_VIEW = True