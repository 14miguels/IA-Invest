import sqlite3
from contextlib import contextmanager
from typing import Generator, Dict, Any, List


import app.config as config
from app.utils import assets_to_csv


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite connections."""
    config.ensure_data_dir()
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Initialize database and create tables."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                source TEXT,
                url TEXT UNIQUE,
                published_at TEXT,
                summary TEXT,
                raw_text TEXT,
                sentiment TEXT,
                theme TEXT,
                assets TEXT,
                impact_score INTEGER,
                short_reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                action TEXT,
                assets TEXT,
                confidence INTEGER,
                position_size REAL,
                reason TEXT,
                theme TEXT,
                sentiment TEXT,
                impact_score INTEGER,
                technical_bias TEXT,
                risk_reason TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Backward-compatible schema patching for older local DB files.
        cursor.execute("PRAGMA table_info(signals)")
        signal_columns = {row[1] for row in cursor.fetchall()}

        if "position_size" not in signal_columns:
            cursor.execute("ALTER TABLE signals ADD COLUMN position_size REAL")
        if "technical_bias" not in signal_columns:
            cursor.execute("ALTER TABLE signals ADD COLUMN technical_bias TEXT")
        if "risk_reason" not in signal_columns:
            cursor.execute("ALTER TABLE signals ADD COLUMN risk_reason TEXT")

        conn.commit()


def insert_news(article: Dict[str, Any]) -> bool:
    """
    Insert a news article into the database.
    Returns True if inserted, False if duplicate.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        title = article.get("title")
        source = article.get("source")
        url = article.get("url")
        published_at = article.get("published_at")

        # Deduplicate explicitly because SQLite UNIQUE on nullable URL allows multiple NULLs.
        if url:
            cursor.execute("SELECT 1 FROM news WHERE url = ? LIMIT 1", (url,))
        else:
            cursor.execute(
                """
                SELECT 1 FROM news
                WHERE title = ? AND source = ? AND COALESCE(published_at, '') = COALESCE(?, '')
                LIMIT 1
                """,
                (title, source, published_at),
            )

        if cursor.fetchone() is not None:
            return False

        try:
            cursor.execute(
                """
                INSERT INTO news (
                    title, source, url, published_at, summary, raw_text,
                    sentiment, theme, assets, impact_score, short_reason
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    title,
                    source,
                    url,
                    published_at,
                    article.get("summary"),
                    article.get("raw_text"),
                    article.get("sentiment"),
                    article.get("theme"),
                    assets_to_csv(article.get("assets", [])),
                    article.get("impact_score"),
                    article.get("short_reason"),
                ),
            )
            conn.commit()
            return True

        except sqlite3.IntegrityError:
            # Duplicate (same URL)
            return False


def insert_signal(signal_data: Dict[str, Any]) -> None:
    """Insert a generated signal into the database."""
    technicals = signal_data.get("technicals") or {}

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO signals (
                title, action, assets, confidence, position_size, reason,
                theme, sentiment, impact_score, technical_bias, risk_reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signal_data.get("title"),
                signal_data.get("action"),
                assets_to_csv(signal_data.get("assets", [])),
                signal_data.get("confidence"),
                signal_data.get("position_size"),
                signal_data.get("reason"),
                signal_data.get("theme"),
                signal_data.get("sentiment"),
                signal_data.get("impact_score"),
                signal_data.get("technical_bias") or technicals.get("technical_bias"),
                signal_data.get("risk_reason"),
            ),
        )
        conn.commit()


def get_latest_news(limit: int = 10) -> list[sqlite3.Row]:
    """Fetch latest news articles ordered by most recent."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM news
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )

        return cursor.fetchall()


if __name__ == "__main__":
    init_db()
    print("Database initialized.")