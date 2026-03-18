import logging
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.backtester import load_tracked_performance, summarize_tracked_performance
from data.portfolio_loader import get_portfolio, get_portfolio_summary as load_portfolio_summary
from data.portfolio_manager import PortfolioManagerError, evaluate_signal_against_portfolio
from data.open_trades_manager import load_open_trades, summarize_open_trades

try:
    from config import DB_PATH
except ModuleNotFoundError:
    from dashboard.config import DB_PATH


logger = logging.getLogger(__name__)


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _get_table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {str(row[1]) for row in cursor.fetchall()}


def _split_assets(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(a).strip() for a in value if str(a).strip()]
    if isinstance(value, str):
        return [a.strip() for a in value.split(",") if a.strip()]
    return []


# --- Portfolio context helpers ---

def _attach_portfolio_context(signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Attach portfolio rows + portfolio decision to each signal for dashboard rendering."""
    try:
        portfolio_rows = get_portfolio()
    except Exception:
        portfolio_rows = []

    enriched: List[Dict[str, Any]] = []

    for signal in signals:
        signal_copy = dict(signal)
        assets = signal_copy.get("assets") or []
        normalized_assets = [str(asset).upper().strip() for asset in assets if str(asset).strip()]

        matching_rows = [
            row for row in portfolio_rows if str(row.get("ticker") or "") in normalized_assets
        ]
        open_positions = [row for row in matching_rows if row.get("status") == "open_position"]
        pending_orders = [row for row in matching_rows if row.get("status") == "pending_order"]

        signal_copy["portfolio_open_positions"] = open_positions
        signal_copy["portfolio_pending_orders"] = pending_orders
        signal_copy["portfolio_has_position"] = bool(open_positions)
        signal_copy["portfolio_has_pending_order"] = bool(pending_orders)

        try:
            decision = evaluate_signal_against_portfolio(signal_copy, portfolio=portfolio_rows)
            signal_copy["portfolio_decision"] = decision.get("portfolio_decision")
            signal_copy["portfolio_decision_reason"] = decision.get("reason")
            signal_copy["portfolio_decisions_by_asset"] = decision.get("decisions_by_asset", {})
        except PortfolioManagerError:
            signal_copy["portfolio_decision"] = None
            signal_copy["portfolio_decision_reason"] = None
            signal_copy["portfolio_decisions_by_asset"] = {}

        enriched.append(signal_copy)

    return enriched


def get_portfolio_rows() -> List[Dict[str, Any]]:
    """Load raw portfolio rows (positions + pending orders) for dashboard use."""
    return get_portfolio()


def get_portfolio_summary() -> Dict[str, Any]:
    """Load small aggregated portfolio metrics for dashboard cards."""
    return load_portfolio_summary()


def get_latest_signals(limit: int = 100) -> List[Dict[str, Any]]:
    """Fetch latest signals from DB, tolerating schema differences."""
    conn = _get_connection()

    try:
        signal_columns = _get_table_columns(conn, "signals")
        if not signal_columns:
            return []

        requested_columns = [
            "title",
            "action",
            "assets",
            "confidence",
            "position_size",
            "reason",
            "theme",
            "sentiment",
            "technical_bias",
            "risk_reason",
            "created_at",
        ]
        selected_columns = [col for col in requested_columns if col in signal_columns]

        if not selected_columns:
            return []

        order_by = "created_at DESC" if "created_at" in signal_columns else "rowid DESC"
        sql = f"SELECT {', '.join(selected_columns)} FROM signals ORDER BY {order_by} LIMIT ?"

        cursor = conn.cursor()
        cursor.execute(sql, (limit,))
        rows = cursor.fetchall()

        results: List[Dict[str, Any]] = []
        for row in rows:
            row_dict = dict(row)
            results.append(
                {
                    "title": row_dict.get("title"),
                    "action": row_dict.get("action"),
                    "assets": _split_assets(row_dict.get("assets")),
                    "confidence": row_dict.get("confidence"),
                    "position_size": row_dict.get("position_size"),
                    "reason": row_dict.get("reason"),
                    "theme": row_dict.get("theme"),
                    "sentiment": row_dict.get("sentiment"),
                    "technical_bias": row_dict.get("technical_bias"),
                    "risk_reason": row_dict.get("risk_reason"),
                    "published_at": row_dict.get("created_at"),
                }
            )
        return _attach_portfolio_context(results)

    except sqlite3.OperationalError as exc:
        logger.warning("Database operational error when querying signals: %s", exc)
        return []
    finally:
        conn.close()


def get_latest_articles(limit: int = 100) -> List[Dict[str, Any]]:
    """Fetch latest articles from DB, tolerating schema differences."""
    conn = _get_connection()

    try:
        news_columns = _get_table_columns(conn, "news")
        if not news_columns:
            return []

        requested_columns = [
            "title",
            "summary",
            "source",
            "theme",
            "sentiment",
            "impact_score",
            "assets",
            "published_at",
            "created_at",
        ]
        selected_columns = [col for col in requested_columns if col in news_columns]

        if not selected_columns:
            return []

        order_by = "created_at DESC" if "created_at" in news_columns else "rowid DESC"
        sql = f"SELECT {', '.join(selected_columns)} FROM news ORDER BY {order_by} LIMIT ?"

        cursor = conn.cursor()
        cursor.execute(sql, (limit,))
        rows = cursor.fetchall()

        results: List[Dict[str, Any]] = []
        for row in rows:
            row_dict = dict(row)
            results.append(
                {
                    "title": row_dict.get("title"),
                    "summary": row_dict.get("summary"),
                    "source": row_dict.get("source"),
                    "theme": row_dict.get("theme"),
                    "sentiment": row_dict.get("sentiment"),
                    "impact_score": row_dict.get("impact_score"),
                    "assets": _split_assets(row_dict.get("assets")),
                    "published_at": row_dict.get("published_at") or row_dict.get("created_at"),
                }
            )

        return results

    except sqlite3.OperationalError as exc:
        logger.warning("Database operational error when querying news: %s", exc)
        return []
    finally:
        conn.close()


def get_tracked_performance(limit: int = 100) -> List[Dict[str, Any]]:
    """Load tracked performance rows from SQLite for the dashboard."""
    return load_tracked_performance(limit=limit)



def get_tracked_performance_summary(limit: int = 500) -> Dict[str, Any]:
    """Load aggregated tracked performance metrics for the dashboard."""
    return summarize_tracked_performance(limit=limit)


def get_open_trades(limit: int = 100) -> List[Dict[str, Any]]:
    """Load open trades from SQLite for the dashboard."""
    return load_open_trades(limit=limit)


def get_open_trades_summary() -> Dict[str, Any]:
    """Load aggregated open-trade metrics for the dashboard."""
    return summarize_open_trades()