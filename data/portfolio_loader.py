

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from data.portfolio_manager import load_portfolio, summarize_portfolio


DEFAULT_PORTFOLIO_PATH = Path(__file__).resolve().parent / "portfolio.json"


# =========================
# BASIC LOADERS
# =========================
def get_portfolio() -> List[Dict[str, Any]]:
    """Return full portfolio (positions + orders)."""
    return load_portfolio(DEFAULT_PORTFOLIO_PATH)



def get_open_positions() -> List[Dict[str, Any]]:
    portfolio = load_portfolio(DEFAULT_PORTFOLIO_PATH)
    return [row for row in portfolio if row.get("status") == "open_position"]



def get_pending_orders() -> List[Dict[str, Any]]:
    portfolio = load_portfolio(DEFAULT_PORTFOLIO_PATH)
    return [row for row in portfolio if row.get("status") == "pending_order"]


# =========================
# DASHBOARD HELPERS
# =========================
def get_portfolio_summary() -> Dict[str, Any]:
    """Small summary for UI cards."""
    return summarize_portfolio(portfolio_path=DEFAULT_PORTFOLIO_PATH)



def get_positions_by_ticker() -> Dict[str, List[Dict[str, Any]]]:
    """Group positions/orders by ticker for easier UI rendering."""
    portfolio = load_portfolio(DEFAULT_PORTFOLIO_PATH)

    grouped: Dict[str, List[Dict[str, Any]]] = {}

    for row in portfolio:
        ticker = row.get("ticker")
        if not ticker:
            continue

        if ticker not in grouped:
            grouped[ticker] = []

        grouped[ticker].append(row)

    return grouped


# =========================
# SIGNAL INTEGRATION
# =========================
def attach_portfolio_to_signals(signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Adds portfolio context (positions/orders) to each signal.
    Useful for UI rendering.
    """
    portfolio = load_portfolio(DEFAULT_PORTFOLIO_PATH)

    enriched = []

    for signal in signals:
        assets = signal.get("assets") or []
        ticker = assets[0] if assets else None

        if ticker:
            rows = [r for r in portfolio if r.get("ticker") == ticker]
            open_positions = [r for r in rows if r.get("status") == "open_position"]
            pending_orders = [r for r in rows if r.get("status") == "pending_order"]
        else:
            open_positions = []
            pending_orders = []

        enriched_signal = dict(signal)
        enriched_signal["portfolio_open_positions"] = open_positions
        enriched_signal["portfolio_pending_orders"] = pending_orders

        enriched.append(enriched_signal)

    return enriched