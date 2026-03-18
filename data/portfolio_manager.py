from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


class PortfolioManagerError(Exception):
    """Raised when portfolio loading or decision logic fails."""


DEFAULT_PORTFOLIO_PATH = Path(__file__).resolve().parent / "portfolio.json"

LONG_SIDES = {"BUY", "LONG"}
SHORT_SIDES = {"SELL", "SHORT"}
ACTIONABLE_SIGNAL_ACTIONS = {"BUY", "SELL"}


@dataclass
class PortfolioDecision:
    ticker: str
    signal_action: str
    portfolio_decision: str
    reason: str
    confidence: int
    signal_position_size: float
    current_exposure_units: float
    pending_order_units: float
    open_position_count: int
    pending_order_count: int
    matching_positions: List[Dict[str, Any]]
    matching_orders: List[Dict[str, Any]]
    decisions_by_asset: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =========================
# LOADING HELPERS
# =========================
def load_portfolio(path: str | Path = DEFAULT_PORTFOLIO_PATH) -> List[Dict[str, Any]]:
    """Load the current paper-trading portfolio snapshot from JSON."""
    portfolio_path = Path(path)
    if not portfolio_path.exists():
        raise PortfolioManagerError(f"Portfolio file not found: {portfolio_path}")

    try:
        data = json.loads(portfolio_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PortfolioManagerError(f"Invalid portfolio JSON: {exc}") from exc

    if not isinstance(data, list):
        raise PortfolioManagerError("Portfolio JSON must contain a list of positions/orders.")

    normalized: List[Dict[str, Any]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        normalized.append(_normalize_portfolio_row(row))

    return normalized



def _normalize_portfolio_row(row: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(row)
    normalized["ticker"] = str(row.get("ticker") or "").upper().strip()
    normalized["instrument"] = str(row.get("instrument") or "").strip()
    normalized["side"] = str(row.get("side") or "").upper().strip()
    normalized["status"] = str(row.get("status") or "").lower().strip()
    normalized["order_type"] = str(row.get("order_type") or "").upper().strip()
    normalized["product_type"] = str(row.get("product_type") or "").upper().strip()
    normalized["quantity"] = float(row.get("quantity") or 0.0)
    normalized["entry_price"] = _safe_float(row.get("entry_price"))
    normalized["current_price"] = _safe_float(row.get("current_price"))
    normalized["stop_loss"] = _safe_float(row.get("stop_loss"))
    normalized["take_profit"] = _safe_float(row.get("take_profit"))
    normalized["duration"] = str(row.get("duration") or "").strip()
    normalized["orders"] = int(row.get("orders") or 0)
    return normalized



def _safe_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# =========================
# FILTERING HELPERS
# =========================
def get_open_positions(portfolio: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [row for row in portfolio if row.get("status") == "open_position"]



def get_pending_orders(portfolio: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [row for row in portfolio if row.get("status") == "pending_order"]



def get_rows_for_ticker(portfolio: List[Dict[str, Any]], ticker: str) -> List[Dict[str, Any]]:
    normalized_ticker = str(ticker or "").upper().strip()
    return [row for row in portfolio if str(row.get("ticker") or "") == normalized_ticker]



def _side_matches_signal(position_side: Any, signal_action: str) -> bool:
    position_side = str(position_side or "").upper().strip()
    signal_action = str(signal_action or "").upper().strip()

    if signal_action == "BUY":
        return position_side in LONG_SIDES
    if signal_action == "SELL":
        return position_side in SHORT_SIDES
    return False



def _side_conflicts_signal(position_side: Any, signal_action: str) -> bool:
    position_side = str(position_side or "").upper().strip()
    signal_action = str(signal_action or "").upper().strip()

    if signal_action == "BUY":
        return position_side in SHORT_SIDES
    if signal_action == "SELL":
        return position_side in LONG_SIDES
    return False


# =========================
# DECISION ENGINE
# =========================
def evaluate_signal_against_portfolio(
    signal: Dict[str, Any],
    portfolio: Optional[List[Dict[str, Any]]] = None,
    portfolio_path: str | Path = DEFAULT_PORTFOLIO_PATH,
) -> Dict[str, Any]:
    """Compare a generated signal against the current portfolio and pending orders."""
    if portfolio is None:
        portfolio = load_portfolio(portfolio_path)

    assets = signal.get("assets") or []
    action = str(signal.get("final_action") or signal.get("action") or "").upper().strip()
    confidence = int(signal.get("confidence") or 0)
    position_size = float(signal.get("position_size") or 0.0)

    if action not in ACTIONABLE_SIGNAL_ACTIONS:
        return {
            "ticker": "",
            "signal_action": action or "HOLD",
            "portfolio_decision": "IGNORE_SIGNAL",
            "reason": "Signal is not actionable for portfolio execution.",
            "confidence": confidence,
            "signal_position_size": position_size,
            "current_exposure_units": 0.0,
            "pending_order_units": 0.0,
            "open_position_count": 0,
            "pending_order_count": 0,
            "matching_positions": [],
            "matching_orders": [],
            "decisions_by_asset": {},
        }

    if not assets:
        raise PortfolioManagerError("Signal has no assets to compare against the portfolio.")

    decisions_by_asset: Dict[str, str] = {}
    asset_details: Dict[str, Dict[str, Any]] = {}

    for asset in assets:
        ticker = str(asset).upper().strip()
        ticker_rows = get_rows_for_ticker(portfolio, ticker)

        open_positions = [row for row in ticker_rows if row.get("status") == "open_position"]
        pending_orders = [row for row in ticker_rows if row.get("status") == "pending_order"]

        aligned_positions = [row for row in open_positions if _side_matches_signal(row.get("side"), action)]
        conflicting_positions = [row for row in open_positions if _side_conflicts_signal(row.get("side"), action)]

        aligned_orders = [row for row in pending_orders if _side_matches_signal(row.get("side"), action)]
        conflicting_orders = [row for row in pending_orders if _side_conflicts_signal(row.get("side"), action)]

        current_exposure_units = round(sum(float(row.get("quantity") or 0.0) for row in aligned_positions), 2)
        pending_order_units = round(sum(float(row.get("quantity") or 0.0) for row in aligned_orders), 2)

        decision = "OPEN_NEW_POSITION"
        reason = "No matching position or order exists; signal can open a new position."

        if conflicting_positions:
            decision = "REDUCE_OR_CLOSE"
            reason = "Signal conflicts with an existing open position on the same asset."
        elif conflicting_orders:
            decision = "REDUCE_OR_CLOSE"
            reason = "Signal conflicts with an existing pending order on the same asset."
        elif aligned_orders:
            decision = "HOLD_EXISTING_ORDER"
            reason = "A matching pending order already exists for this asset."
        elif aligned_positions:
            if confidence >= 5 and position_size >= 0.7:
                decision = "ADD_TO_POSITION"
                reason = "A matching open position exists and the new signal is strong enough to justify adding."
            else:
                decision = "HOLD_POSITION"
                reason = "A matching open position already exists; holding is preferred over adding here."
        elif confidence < 3 or position_size <= 0:
            decision = "IGNORE_SIGNAL"
            reason = "Signal conviction is too weak for portfolio execution."

        decisions_by_asset[ticker] = decision
        asset_details[ticker] = {
            "current_exposure_units": current_exposure_units,
            "pending_order_units": pending_order_units,
            "open_position_count": len(open_positions),
            "pending_order_count": len(pending_orders),
            "matching_positions": open_positions,
            "matching_orders": pending_orders,
            "reason": reason,
        }

    priority = [
        "REDUCE_OR_CLOSE",
        "HOLD_EXISTING_ORDER",
        "HOLD_POSITION",
        "ADD_TO_POSITION",
        "OPEN_NEW_POSITION",
        "IGNORE_SIGNAL",
    ]

    final_decision = "OPEN_NEW_POSITION"
    for decision_name in priority:
        if decision_name in decisions_by_asset.values():
            final_decision = decision_name
            break

    representative_ticker = str(assets[0]).upper().strip()
    representative = asset_details.get(
        representative_ticker,
        {
            "current_exposure_units": 0.0,
            "pending_order_units": 0.0,
            "open_position_count": 0,
            "pending_order_count": 0,
            "matching_positions": [],
            "matching_orders": [],
            "reason": "Multi-asset evaluation",
        },
    )

    return PortfolioDecision(
        ticker=representative_ticker,
        signal_action=action,
        portfolio_decision=final_decision,
        reason="Multi-asset evaluation",
        confidence=confidence,
        signal_position_size=position_size,
        current_exposure_units=representative["current_exposure_units"],
        pending_order_units=representative["pending_order_units"],
        open_position_count=representative["open_position_count"],
        pending_order_count=representative["pending_order_count"],
        matching_positions=representative["matching_positions"],
        matching_orders=representative["matching_orders"],
        decisions_by_asset=decisions_by_asset,
    ).to_dict()



def evaluate_signals_against_portfolio(
    signals: List[Dict[str, Any]],
    portfolio: Optional[List[Dict[str, Any]]] = None,
    portfolio_path: str | Path = DEFAULT_PORTFOLIO_PATH,
) -> List[Dict[str, Any]]:
    """Evaluate a batch of signals against the current portfolio snapshot."""
    if portfolio is None:
        portfolio = load_portfolio(portfolio_path)

    decisions: List[Dict[str, Any]] = []
    for signal in signals:
        try:
            decisions.append(evaluate_signal_against_portfolio(signal, portfolio=portfolio))
        except PortfolioManagerError:
            continue

    return decisions



def summarize_portfolio(
    portfolio: Optional[List[Dict[str, Any]]] = None,
    portfolio_path: str | Path = DEFAULT_PORTFOLIO_PATH,
) -> Dict[str, Any]:
    """Return a small summary of the current portfolio snapshot."""
    if portfolio is None:
        portfolio = load_portfolio(portfolio_path)

    open_positions = get_open_positions(portfolio)
    pending_orders = get_pending_orders(portfolio)

    tickers = sorted({str(row.get("ticker") or "") for row in portfolio if str(row.get("ticker") or "")})

    return {
        "rows": len(portfolio),
        "open_positions": len(open_positions),
        "pending_orders": len(pending_orders),
        "tracked_tickers": tickers,
    }