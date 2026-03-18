from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
import yfinance as yf


class OpenTradesManagerError(Exception):
    """Raised when open trade management fails."""


DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "invest.db"


YFINANCE_MAP = {
    "OIL": "USO",
    "GOLD": "GLD",
}


UNSUPPORTED_LIVE_PRICE_ASSETS = {
    "ALUMINUM",
    "ALUMINIUM",
}

INTRADAY_PRICE_WINDOWS = [
    ("1d", "1m"),
    ("5d", "5m"),
    ("1mo", "1d"),
]


# =========================
# DB HELPERS
# =========================
def _get_connection(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn



def init_open_trades(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Create the open_trades table if it does not exist."""
    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS open_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                asset TEXT,
                action TEXT,
                confidence INTEGER,
                position_size REAL,
                timestamp TEXT,
                entry_price REAL,
                current_price REAL,
                unrealized_return_pct REAL,
                days_open INTEGER,
                status TEXT DEFAULT 'open',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_price_update_at TEXT
            )
            """
        )
        conn.commit()

    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(open_trades)")
        columns = {row[1] for row in cursor.fetchall()}
        if "last_price_update_at" not in columns:
            cursor.execute("ALTER TABLE open_trades ADD COLUMN last_price_update_at TEXT")
            conn.commit()


# =========================
# CORE HELPERS
# =========================
def _normalize_asset(asset: str) -> str:
    asset = str(asset or "").upper().strip()
    return YFINANCE_MAP.get(asset, asset)


def _extract_scalar_close(value: Any) -> float:
    if hasattr(value, "iloc"):
        try:
            return float(value.iloc[0])
        except Exception:
            pass
    return float(value)


def _resolve_live_price(asset: str) -> float:
    raw_asset = str(asset or "").upper().strip()
    if not raw_asset:
        raise OpenTradesManagerError("Missing asset for live price resolution.")
    if raw_asset in UNSUPPORTED_LIVE_PRICE_ASSETS:
        raise OpenTradesManagerError(f"Asset is not supported for live pricing: {raw_asset}")

    ticker = _normalize_asset(raw_asset)
    last_error: Exception | None = None

    for period, interval in INTRADAY_PRICE_WINDOWS:
        try:
            data = yf.download(
                ticker,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=True,
                prepost=False,
            )
        except Exception as exc:
            last_error = exc
            continue

        if data is None or data.empty:
            continue

        closes = data["Close"].dropna()
        if closes.empty:
            continue

        last_value = closes.iloc[-1]
        return round(_extract_scalar_close(last_value), 2)

    if last_error is not None:
        raise OpenTradesManagerError(f"Failed to fetch live price for {ticker}: {last_error}")
    raise OpenTradesManagerError(f"No live market data found for {ticker}.")



def _parse_timestamp(value: Any) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise OpenTradesManagerError("Missing trade timestamp.")

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue

    try:
        return datetime.fromisoformat(raw)
    except ValueError as exc:
        raise OpenTradesManagerError(f"Unsupported timestamp format: {raw}") from exc



def _compute_unrealized_return_pct(action: str, entry_price: float, current_price: float) -> float:
    if entry_price <= 0:
        raise OpenTradesManagerError("Entry price must be positive.")

    raw_return = ((current_price - entry_price) / entry_price) * 100.0
    if str(action or "").upper().strip() == "SELL":
        raw_return *= -1.0

    return round(raw_return, 2)



def _days_open(timestamp: Any) -> int:
    start_dt = _parse_timestamp(timestamp)
    delta = datetime.now() - start_dt
    return max(delta.days, 0)


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# =========================
# INSERT / LOAD
# =========================
def add_open_trade(signal: Dict[str, Any], db_path: str | Path = DEFAULT_DB_PATH) -> int:
    """
    Insert a new open trade from a generated signal.

    Expected fields:
    - title
    - action
    - assets
    - confidence
    - position_size
    - timestamp / published_at / created_at
    - entry_price (optional; if missing, current_price is used)
    - current_price (optional)
    """
    init_open_trades(db_path)

    title = str(signal.get("title") or "")
    action = str(signal.get("final_action") or signal.get("action") or "").upper().strip()
    assets = signal.get("assets") or []
    confidence = int(signal.get("confidence") or 0)
    position_size = float(signal.get("position_size") or 0.0)
    timestamp = signal.get("timestamp") or signal.get("published_at") or signal.get("created_at")

    if action not in {"BUY", "SELL"}:
        raise OpenTradesManagerError(f"Open trade action must be BUY or SELL, got: {action!r}")
    if not assets:
        raise OpenTradesManagerError("Signal has no tradable assets.")
    if not timestamp:
        raise OpenTradesManagerError("Signal has no timestamp.")

    asset = _normalize_asset(str(assets[0]))
    entry_price = signal.get("entry_price")
    current_price = signal.get("current_price")

    if entry_price in (None, ""):
        if current_price in (None, ""):
            raise OpenTradesManagerError("Either entry_price or current_price must be provided.")
        entry_price = float(current_price)
    else:
        entry_price = float(entry_price)

    if current_price in (None, ""):
        current_price = float(entry_price)
    else:
        current_price = float(current_price)

    unrealized_return_pct = _compute_unrealized_return_pct(action, entry_price, current_price)
    days_open = _days_open(timestamp)

    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO open_trades (
                title, asset, action, confidence, position_size, timestamp,
                entry_price, current_price, unrealized_return_pct, days_open, status,
                last_price_update_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)
            """,
            (
                title,
                asset,
                action,
                confidence,
                position_size,
                str(timestamp),
                round(entry_price, 2),
                round(current_price, 2),
                unrealized_return_pct,
                days_open,
                _now_utc_iso(),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)



def load_open_trades(limit: int = 100, db_path: str | Path = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Load recent open trades from SQLite."""
    init_open_trades(db_path)

    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                id, title, asset, action, confidence, position_size, timestamp,
                entry_price, current_price, unrealized_return_pct, days_open,
                status, created_at, last_price_update_at
            FROM open_trades
            WHERE status = 'open'
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()

    return [dict(row) for row in rows]


def load_open_trade_by_id(trade_id: int, db_path: str | Path = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """Load a single open trade by id."""
    init_open_trades(db_path)

    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                id, title, asset, action, confidence, position_size, timestamp,
                entry_price, current_price, unrealized_return_pct, days_open,
                status, created_at, last_price_update_at
            FROM open_trades
            WHERE id = ?
            """,
            (trade_id,),
        )
        row = cursor.fetchone()

    if row is None:
        raise OpenTradesManagerError(f"Open trade not found for id={trade_id}")

    return dict(row)


# =========================
# UPDATE / CLOSE
# =========================
def update_open_trade_price(
    trade_id: int,
    current_price: float,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> None:
    """Update current price and unrealized return for an open trade."""
    init_open_trades(db_path)

    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, action, entry_price, timestamp
            FROM open_trades
            WHERE id = ? AND status = 'open'
            """,
            (trade_id,),
        )
        row = cursor.fetchone()

        if row is None:
            raise OpenTradesManagerError(f"Open trade not found for id={trade_id}")

        action = str(row["action"])
        entry_price = float(row["entry_price"])
        timestamp = row["timestamp"]

        unrealized_return_pct = _compute_unrealized_return_pct(action, entry_price, float(current_price))
        days_open = _days_open(timestamp)

        cursor.execute(
            """
            UPDATE open_trades
            SET current_price = ?, unrealized_return_pct = ?, days_open = ?, last_price_update_at = ?
            WHERE id = ?
            """,
            (round(float(current_price), 2), unrealized_return_pct, days_open, _now_utc_iso(), trade_id),
        )
        conn.commit()


def update_all_open_trades_prices(db_path: str | Path = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """Refresh all open trades with latest market prices from Yahoo Finance."""
    rows = load_open_trades(limit=5000, db_path=db_path)
    if not rows:
        return {
            "updated": 0,
            "skipped": 0,
            "errors": [],
        }

    updated = 0
    skipped = 0
    errors: List[str] = []

    for row in rows:
        trade_id = int(row["id"])
        asset = str(row.get("asset") or "").upper().strip()

        try:
            live_price = _resolve_live_price(asset)
            update_open_trade_price(trade_id, live_price, db_path=db_path)
            updated += 1
        except OpenTradesManagerError as exc:
            skipped += 1
            errors.append(f"id={trade_id} asset={asset}: {exc}")

    return {
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
    }



def close_open_trade(trade_id: int, db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Mark an open trade as closed."""
    init_open_trades(db_path)

    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE open_trades
            SET status = 'closed'
            WHERE id = ? AND status = 'open'
            """,
            (trade_id,),
        )
        conn.commit()


# Inserted function: close_mature_open_trades
def close_mature_open_trades(max_days: int = 3, db_path: str | Path = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """Close open trades that have been open for >= max_days."""
    init_open_trades(db_path)

    with _get_connection(db_path) as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*) as cnt
            FROM open_trades
            WHERE status = 'open' AND days_open >= ?
            """,
            (max_days,),
        )
        row = cursor.fetchone()
        to_close = int(row["cnt"]) if row else 0

        if to_close == 0:
            return {"closed": 0}

        cursor.execute(
            """
            UPDATE open_trades
            SET status = 'closed'
            WHERE status = 'open' AND days_open >= ?
            """,
            (max_days,),
        )
        conn.commit()

    return {"closed": to_close}


# =========================
# SUMMARY
# =========================
def summarize_open_trades(db_path: str | Path = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """Return a small summary of open trades."""
    rows = load_open_trades(limit=1000, db_path=db_path)
    if not rows:
        return {
            "open_trades": 0,
            "avg_unrealized_return_pct": 0.0,
            "total_unrealized_weighted_return_pct": 0.0,
        }

    count = len(rows)
    avg_unrealized_return_pct = round(
        sum(float(row.get("unrealized_return_pct") or 0.0) for row in rows) / count,
        2,
    )
    total_unrealized_weighted_return_pct = round(
        sum((float(row.get("unrealized_return_pct") or 0.0) * float(row.get("position_size") or 0.0)) for row in rows),
        2,
    )

    return {
        "open_trades": count,
        "avg_unrealized_return_pct": avg_unrealized_return_pct,
        "total_unrealized_weighted_return_pct": total_unrealized_weighted_return_pct,
    }