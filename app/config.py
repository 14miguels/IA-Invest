from pathlib import Path

# =========================
# PATHS
# =========================
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "invest.db"


# =========================
# NEWS SOURCES
# =========================
RSS_FEEDS = [
    {
        "name": "Reuters Markets",
        "url": "https://feeds.reuters.com/reuters/businessNews",
    },
    {
        "name": "Reuters World News",
        "url": "https://feeds.reuters.com/Reuters/worldNews",
    },
    {
        "name": "CNBC Top News",
        "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    },
    {
        "name": "MarketWatch Top Stories",
        "url": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    },
]

REQUEST_TIMEOUT = 15
MAX_NEWS_PER_FEED = 25
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


# =========================
# LLM CONFIG
# =========================
USE_LLM = True
LLM_MODEL = "gemini-2.5-flash"


# =========================
# MARKET DATA CONFIG
# =========================
MARKET_DATA_PROVIDER = "yfinance"  # future: alpha_vantage, polygon, etc.
HISTORY_DAYS = 60


# =========================
# TECHNICAL INDICATORS
# =========================
RSI_PERIOD = 14

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9


# =========================
# SIGNAL ENGINE CONFIG
# =========================
MIN_IMPACT_SCORE = 2

# Confidence tuning
BULLISH_WEIGHT = 1.0
BEARISH_WEIGHT = 1.0
TECHNICAL_WEIGHT = 1.0


# =========================
# UTILITIES
# =========================
def ensure_data_dir() -> None:
    """Create the data directory if it does not exist yet."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)