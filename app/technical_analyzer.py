from typing import Any, Dict, List, Sequence

from app.config import RSI_PERIOD, MACD_FAST, MACD_SLOW, MACD_SIGNAL


class TechnicalAnalysisError(Exception):
    """Raised when technical analysis cannot be computed."""


def _validate_period(period: int, name: str) -> None:
    if period <= 0:
        raise TechnicalAnalysisError(f"{name} period must be greater than zero.")



def _to_float_list(values: Sequence[float]) -> List[float]:
    if not values:
        raise TechnicalAnalysisError("Values must be a non-empty sequence.")
    return [float(value) for value in values]


def _describe_rsi(rsi: float) -> tuple[str, str | None]:
    if rsi < 30:
        return "bullish", "RSI is oversold"
    if rsi > 70:
        return "bearish", "RSI is overbought"
    return "neutral", "RSI is neutral"



def _describe_macd(macd: float, macd_signal: float) -> tuple[str, str]:
    if macd > macd_signal:
        return "bullish", "MACD is above signal line"
    if macd < macd_signal:
        return "bearish", "MACD is below signal line"
    return "neutral", "MACD is in line with signal line"


# =========================
# INDICATORS
# =========================
def calculate_ema(values: Sequence[float], period: int) -> List[float | None]:
    _validate_period(period, "EMA")
    prices = _to_float_list(values)

    if len(prices) < period:
        raise TechnicalAnalysisError("Not enough data to compute EMA.")

    ema_values: List[float | None] = []
    multiplier = 2 / (period + 1)

    sma = sum(prices[:period]) / period
    ema_values.extend([None] * (period - 1))
    ema_values.append(sma)

    for price in prices[period:]:
        prev_ema = ema_values[-1]
        if prev_ema is None:
            raise TechnicalAnalysisError("EMA internal state is invalid.")
        ema = (price - prev_ema) * multiplier + prev_ema
        ema_values.append(ema)

    return ema_values



def calculate_rsi(closes: Sequence[float], period: int = RSI_PERIOD) -> float:
    _validate_period(period, "RSI")
    prices = _to_float_list(closes)

    if len(prices) < period + 1:
        raise TechnicalAnalysisError("Not enough data to compute RSI.")

    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [max(delta, 0.0) for delta in deltas]
    losses = [abs(min(delta, 0.0)) for delta in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(deltas)):
        avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))



def calculate_macd(
    closes: Sequence[float],
    fast: int = MACD_FAST,
    slow: int = MACD_SLOW,
    signal: int = MACD_SIGNAL,
) -> Dict[str, float]:
    _validate_period(fast, "MACD fast")
    _validate_period(slow, "MACD slow")
    _validate_period(signal, "MACD signal")

    if fast >= slow:
        raise TechnicalAnalysisError("MACD fast period must be lower than slow period.")

    prices = _to_float_list(closes)

    if len(prices) < slow + signal:
        raise TechnicalAnalysisError("Not enough data to compute MACD.")

    ema_fast = calculate_ema(prices, fast)
    ema_slow = calculate_ema(prices, slow)

    macd_line: List[float | None] = []
    for f, s in zip(ema_fast, ema_slow):
        if f is None or s is None:
            macd_line.append(None)
        else:
            macd_line.append(f - s)

    valid_macd = [m for m in macd_line if m is not None]
    if len(valid_macd) < signal:
        raise TechnicalAnalysisError("Not enough MACD values to compute signal line.")
    signal_line = calculate_ema(valid_macd, signal)

    return {
        "macd": valid_macd[-1],
        "signal": signal_line[-1],
    }


# =========================
# MAIN ANALYSIS
# =========================
def analyze_technicals(price_data: Dict[str, Any]) -> Dict[str, Any]:
    closes = price_data.get("close") or []
    ticker = price_data.get("ticker", "UNKNOWN")

    if len(closes) < MACD_SLOW + MACD_SIGNAL:
        raise TechnicalAnalysisError("Not enough price data for analysis.")

    rsi = calculate_rsi(closes)
    macd_data = calculate_macd(closes)

    macd = macd_data["macd"]
    macd_signal = macd_data["signal"]

    # =========================
    # BIAS LOGIC
    # =========================
    bullish_signals = 0
    bearish_signals = 0

    rsi_bias, rsi_reason = _describe_rsi(rsi)
    macd_bias, macd_reason = _describe_macd(macd, macd_signal)

    if rsi_bias == "bullish":
        bullish_signals += 1
    elif rsi_bias == "bearish":
        bearish_signals += 1

    if macd_bias == "bullish":
        bullish_signals += 1
    elif macd_bias == "bearish":
        bearish_signals += 1

    if bullish_signals > bearish_signals:
        bias = "bullish"
    elif bearish_signals > bullish_signals:
        bias = "bearish"
    else:
        bias = "neutral"

    reason = f"{rsi_reason} and {macd_reason}."

    return {
        "ticker": ticker,
        "rsi": round(rsi, 2),
        "macd": round(macd, 4),
        "macd_signal": round(macd_signal, 4),
        "technical_bias": bias,
        "technical_reason": reason,
    }