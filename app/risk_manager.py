

from typing import Any, Dict


class RiskManagerError(Exception):
    """Raised when risk evaluation fails."""


# =========================
# CONFIG
# =========================
MAX_POSITION_SIZE = 1.0
MIN_CONFIDENCE_TO_TRADE = 3
REDUCE_ON_CONFLICT = 0.5
REDUCE_ON_NEUTRAL = 0.85


# =========================
# HELPERS
# =========================
def _normalize_action(value: Any) -> str:
    action = str(value or "HOLD").upper().strip()
    if action not in {"BUY", "SELL", "HOLD"}:
        return "HOLD"
    return action



def _extract_technical_bias(signal: Dict[str, Any]) -> str:
    direct_bias = signal.get("technical_bias")
    if direct_bias:
        return str(direct_bias).lower().strip()

    technicals = signal.get("technicals") or {}
    return str(technicals.get("technical_bias") or "neutral").lower().strip()



def _base_position_size(signal: Dict[str, Any], confidence: int, action: str) -> float:
    existing = signal.get("position_size")
    if existing not in (None, ""):
        try:
            return float(existing)
        except (TypeError, ValueError):
            pass

    if action == "HOLD" or confidence < MIN_CONFIDENCE_TO_TRADE:
        return 0.0

    # 3 -> 0.5, 4 -> 0.75, 5 -> 1.0
    size = (confidence - 2) / 3
    return float(min(max(size, 0.0), MAX_POSITION_SIZE))


# =========================
# CORE LOGIC
# =========================
def evaluate_risk(signal: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply simple portfolio/risk rules to a generated signal.

    Input:
    {
        action, assets, confidence, reason, technicals
    }

    Output adds:
    - final_action
    - position_size
    - risk_reason
    """
    try:
        action = _normalize_action(signal.get("action"))
        confidence = int(signal.get("confidence") or 1)
        technical_bias = _extract_technical_bias(signal)
    except Exception as exc:
        raise RiskManagerError(f"Invalid signal format: {exc}") from exc

    # =========================
    # LOW-CONFIDENCE SAFETY
    # =========================
    if action == "HOLD" or confidence < MIN_CONFIDENCE_TO_TRADE:
        return {
            **signal,
            "final_action": "HOLD",
            "position_size": 0.0,
            "risk_reason": "Confidence too low to open position.",
        }

    position_size = _base_position_size(signal, confidence, action)

    # =========================
    # CONFLICT / ALIGNMENT
    # =========================
    if action == "BUY" and technical_bias == "bearish":
        position_size *= REDUCE_ON_CONFLICT
        risk_reason = "Bullish signal but bearish technicals → reduced exposure."

    elif action == "SELL" and technical_bias == "bullish":
        position_size *= REDUCE_ON_CONFLICT
        risk_reason = "Bearish signal but bullish technicals → reduced exposure."

    elif technical_bias == "neutral":
        position_size *= REDUCE_ON_NEUTRAL
        risk_reason = "Technicals are neutral → slightly reduced exposure."

    else:
        risk_reason = "Signal and technicals aligned or neutral."

    position_size = min(max(position_size, 0.0), MAX_POSITION_SIZE)

    # =========================
    # FINAL SAFETY
    # =========================
    final_action = action if position_size > 0 else "HOLD"

    return {
        **signal,
        "final_action": final_action,
        "position_size": round(position_size, 2),
        "risk_reason": risk_reason,
    }


# =========================
# BATCH PROCESSING
# =========================
def evaluate_signals(signals: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """Apply risk management to a list of signals."""
    results = []

    for signal in signals:
        try:
            results.append(evaluate_risk(signal))
        except RiskManagerError:
            continue

    return results