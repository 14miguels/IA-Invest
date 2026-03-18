from __future__ import annotations

import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List

import yfinance as yf


class BacktesterError(Exception):
    """Raised when backtesting data is invalid or unavailable."""


@dataclass
class BacktestTrade:
    title: str
    asset: str
    action: str
    confidence: int
    position_size: float
    timestamp: str
    entry_price: float
    exit_price: float
    holding_days: int
    return_pct: float
    weighted_return_pct: float
    outcome: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BacktestSummary:
    trades: int
    wins: int
    losses: int
    win_rate: float
    avg_return_pct: float
    avg_weighted_return_pct: float
    total_weighted_return_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


YFINANCE_MAP = {
    "OIL": "USO",
    "GOLD": "GLD",
}

VALID_ACTIONS = {"BUY", "SELL"}
DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "invest.db"


# =========================
# BASIC HELPERS
# =========================
def _normalize_asset(asset: str) -> str:
    asset = str(asset or "").upper().strip()
    return YFINANCE_MAP.get(asset, asset)



def _parse_timestamp(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value

    raw = str(value or "").strip()
    if not raw:
        raise BacktesterError("Signal timestamp is missing.")

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
        raise BacktesterError(f"Unsupported timestamp format: {raw}") from exc



def _extract_signal_core(signal: Dict[str, Any]) -> Dict[str, Any]:
    """Accept both raw signal dicts and wrapper dicts."""
    if "signal" in signal and isinstance(signal["signal"], dict):
        core = dict(signal["signal"])
        core.setdefault("title", signal.get("title"))
        core.setdefault("timestamp", signal.get("timestamp") or signal.get("published_at"))
        return core
    return dict(signal)




def _fetch_price_window(ticker: str, start: datetime, end: datetime):
    data = yf.download(
        ticker,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,
    )
    if data is None or data.empty:
        raise BacktesterError(f"No market data found for {ticker}.")
    return data


# Helper to normalize yfinance close values
def _extract_scalar_close(value: Any) -> float:
    """Normalize yfinance close values that may come back as scalar, Series, or 1-row DataFrame slices."""
    if hasattr(value, "iloc"):
        try:
            return float(value.iloc[0])
        except Exception:
            pass
    return float(value)



def _first_valid_close(data) -> float:
    closes = data["Close"].dropna()
    if closes.empty:
        raise BacktesterError("Missing entry close price.")
    return _extract_scalar_close(closes.iloc[0])



def _last_valid_close(data) -> float:
    closes = data["Close"].dropna()
    if closes.empty:
        raise BacktesterError("Missing exit close price.")
    return _extract_scalar_close(closes.iloc[-1])



def _compute_return_pct(action: str, entry_price: float, exit_price: float) -> float:
    if entry_price <= 0:
        raise BacktesterError("Entry price must be positive.")

    raw_return = ((exit_price - entry_price) / entry_price) * 100.0
    if action == "SELL":
        raw_return *= -1.0
    return round(raw_return, 2)



def _trade_outcome(return_pct: float) -> str:
    if return_pct > 0:
        return "win"
    if return_pct < 0:
        return "loss"
    return "flat"


def _candidate_assets(assets: List[str]) -> List[str]:
    """Return normalized unique candidate tickers to try in backtesting order."""
    seen = set()
    candidates: List[str] = []

    for asset in assets:
        normalized = _normalize_asset(str(asset))
        if normalized and normalized not in seen:
            seen.add(normalized)
            candidates.append(normalized)

    return candidates



def _backtest_single_asset(
    title: str,
    asset: str,
    action: str,
    confidence: int,
    position_size: float,
    timestamp: Any,
    holding_days: int,
) -> BacktestTrade:
    start_dt = _parse_timestamp(timestamp)

    # Add buffer because finance APIs treat end date as exclusive and markets close on weekends/holidays.
    fetch_start = start_dt - timedelta(days=2)
    fetch_end = start_dt + timedelta(days=holding_days + 8)

    data = _fetch_price_window(asset, fetch_start, fetch_end)

    entry_slice = data[data.index >= start_dt.strftime("%Y-%m-%d")]
    if entry_slice.empty:
        raise BacktesterError(f"No entry data available on/after signal date for {asset}.")

    entry_price = _first_valid_close(entry_slice.iloc[:3])

    exit_target = start_dt + timedelta(days=holding_days)
    exit_slice = data[data.index >= exit_target.strftime("%Y-%m-%d")]
    if exit_slice.empty:
        raise BacktesterError(f"No exit data available on/after holding window for {asset}.")

    exit_price = _last_valid_close(exit_slice.iloc[:3])
    return_pct = _compute_return_pct(action, entry_price, exit_price)
    weighted_return_pct = round(return_pct * position_size, 2)

    return BacktestTrade(
        title=title,
        asset=asset,
        action=action,
        confidence=confidence,
        position_size=round(position_size, 2),
        timestamp=str(timestamp or ""),
        entry_price=round(entry_price, 2),
        exit_price=round(exit_price, 2),
        holding_days=holding_days,
        return_pct=return_pct,
        weighted_return_pct=weighted_return_pct,
        outcome=_trade_outcome(return_pct),
    )



# =========================
# CORE BACKTESTING
# =========================
def backtest_signal(signal: Dict[str, Any], holding_days: int = 3) -> BacktestTrade:
    """
    Backtest one signal over a fixed holding window.

    Expected fields in `signal`:
    - title
    - action (BUY/SELL)
    - assets (list[str])
    - confidence
    - position_size
    - timestamp or published_at
    """
    if holding_days < 1:
        raise BacktesterError("holding_days must be at least 1.")

    core = _extract_signal_core(signal)

    title = str(core.get("title") or "")
    action = str(core.get("final_action") or core.get("action") or "").upper().strip()
    assets = core.get("assets") or []
    confidence = int(core.get("confidence") or 0)
    position_size = float(core.get("position_size") or 0.0)
    timestamp = core.get("timestamp") or core.get("published_at") or core.get("created_at")

    if action not in VALID_ACTIONS:
        raise BacktesterError(f"Signal action must be BUY or SELL, got: {action!r}")
    if not assets:
        raise BacktesterError("Signal has no tradable assets.")

    candidate_assets = _candidate_assets([str(asset) for asset in assets])
    if not candidate_assets:
        raise BacktesterError("Signal has no valid normalized assets.")

    last_error: BacktesterError | None = None
    for asset in candidate_assets:
        try:
            return _backtest_single_asset(
                title=title,
                asset=asset,
                action=action,
                confidence=confidence,
                position_size=position_size,
                timestamp=timestamp,
                holding_days=holding_days,
            )
        except BacktesterError as exc:
            last_error = exc
            continue

    raise last_error or BacktesterError("Unable to backtest signal for any candidate asset.")



def backtest_signals(
    signals: Iterable[Dict[str, Any]],
    holding_days: int = 3,
    skip_errors: bool = True,
) -> List[Dict[str, Any]]:
    """Backtest a batch of signals and return a list of trade dictionaries."""
    results: List[Dict[str, Any]] = []

    for signal in signals:
        try:
            trade = backtest_signal(signal, holding_days=holding_days)
            results.append(trade.to_dict())
        except BacktesterError as exc:
            if not skip_errors:
                raise
            # Silently skip invalid/unavailable trades in batch mode, but keep a hint for debugging.
            continue

    return results



def summarize_backtest(trades: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    trade_list = list(trades)
    if not trade_list:
        return BacktestSummary(
            trades=0,
            wins=0,
            losses=0,
            win_rate=0.0,
            avg_return_pct=0.0,
            avg_weighted_return_pct=0.0,
            total_weighted_return_pct=0.0,
        ).to_dict()

    wins = sum(1 for trade in trade_list if float(trade.get("return_pct", 0)) > 0)
    losses = sum(1 for trade in trade_list if float(trade.get("return_pct", 0)) < 0)
    total = len(trade_list)

    avg_return_pct = round(
        sum(float(trade.get("return_pct", 0)) for trade in trade_list) / total,
        2,
    )
    avg_weighted_return_pct = round(
        sum(float(trade.get("weighted_return_pct", 0)) for trade in trade_list) / total,
        2,
    )
    total_weighted_return_pct = round(
        sum(float(trade.get("weighted_return_pct", 0)) for trade in trade_list),
        2,
    )

    summary = BacktestSummary(
        trades=total,
        wins=wins,
        losses=losses,
        win_rate=round((wins / total) * 100.0, 2),
        avg_return_pct=avg_return_pct,
        avg_weighted_return_pct=avg_weighted_return_pct,
        total_weighted_return_pct=total_weighted_return_pct,
    )
    return summary.to_dict()



def backtest_and_summarize(
    signals: Iterable[Dict[str, Any]],
    holding_days: int = 3,
    skip_errors: bool = True,
) -> Dict[str, Any]:
    trades = backtest_signals(signals, holding_days=holding_days, skip_errors=skip_errors)
    return {
        "trades": trades,
        "summary": summarize_backtest(trades),
    }


# =========================
# PERFORMANCE TRACKING (PERSISTENCE)
# =========================
def _get_connection(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn



def init_performance_tracking(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Create the performance tracking table if it does not exist."""
    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS performance_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                asset TEXT,
                action TEXT,
                confidence INTEGER,
                position_size REAL,
                timestamp TEXT,
                entry_price REAL,
                exit_price REAL,
                holding_days INTEGER,
                return_pct REAL,
                weighted_return_pct REAL,
                outcome TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()



def save_backtest_trades(
    trades: Iterable[Dict[str, Any]],
    db_path: str | Path = DEFAULT_DB_PATH,
) -> int:
    """Persist backtested trades into the performance_tracking table."""
    trade_list = list(trades)
    if not trade_list:
        return 0

    init_performance_tracking(db_path)

    inserted = 0
    with _get_connection(db_path) as conn:
        cursor = conn.cursor()

        for trade in trade_list:
            cursor.execute(
                """
                INSERT INTO performance_tracking (
                    title, asset, action, confidence, position_size, timestamp,
                    entry_price, exit_price, holding_days, return_pct,
                    weighted_return_pct, outcome
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade.get("title"),
                    trade.get("asset"),
                    trade.get("action"),
                    trade.get("confidence"),
                    trade.get("position_size"),
                    trade.get("timestamp"),
                    trade.get("entry_price"),
                    trade.get("exit_price"),
                    trade.get("holding_days"),
                    trade.get("return_pct"),
                    trade.get("weighted_return_pct"),
                    trade.get("outcome"),
                ),
            )
            inserted += 1

        conn.commit()

    return inserted



def load_tracked_performance(
    limit: int = 100,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> List[Dict[str, Any]]:
    """Load recent tracked performance rows from SQLite."""
    init_performance_tracking(db_path)

    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                title, asset, action, confidence, position_size, timestamp,
                entry_price, exit_price, holding_days, return_pct,
                weighted_return_pct, outcome, created_at
            FROM performance_tracking
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()

    return [dict(row) for row in rows]



def summarize_tracked_performance(
    limit: int = 500,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> Dict[str, Any]:
    """Summarize recent persisted tracked performance."""
    rows = load_tracked_performance(limit=limit, db_path=db_path)
    return summarize_backtest(rows)



def backtest_track_and_summarize(
    signals: Iterable[Dict[str, Any]],
    holding_days: int = 3,
    skip_errors: bool = True,
    db_path: str | Path = DEFAULT_DB_PATH,
) -> Dict[str, Any]:
    """Run backtest, persist trades, and return summary in one step."""
    trades = backtest_signals(signals, holding_days=holding_days, skip_errors=skip_errors)
    inserted = save_backtest_trades(trades, db_path=db_path)
    return {
        "inserted": inserted,
        "trades": trades,
        "summary": summarize_backtest(trades),
    }