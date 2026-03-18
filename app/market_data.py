

from typing import Any, Dict, List

import yfinance as yf

from app.config import HISTORY_DAYS, MARKET_DATA_PROVIDER


class MarketDataError(Exception):
    """Raised when market data cannot be retrieved or validated."""



def _validate_ticker(ticker: str) -> str:
    """Validate and normalize a ticker symbol."""
    normalized = (ticker or "").strip().upper()
    if not normalized:
        raise MarketDataError("Ticker must be a non-empty string.")
    return normalized



def _validate_provider() -> None:
    """Validate the configured market data provider."""
    if MARKET_DATA_PROVIDER != "yfinance":
        raise MarketDataError(
            f"Unsupported market data provider: {MARKET_DATA_PROVIDER}"
        )



def _series_to_float_list(series: Any) -> List[float]:
    """Convert a pandas Series to a clean list of floats, dropping NaN values."""
    if series is None:
        return []

    cleaned = series.dropna().tolist()
    return [float(value) for value in cleaned]



def get_price_history(ticker: str, period_days: int = HISTORY_DAYS) -> Dict[str, Any]:
    """Fetch recent OHLCV history for a ticker using yfinance."""
    _validate_provider()
    symbol = _validate_ticker(ticker)

    if period_days <= 0:
        raise MarketDataError("period_days must be greater than zero.")

    try:
        history = yf.Ticker(symbol).history(period=f"{period_days}d", auto_adjust=False)
    except Exception as exc:
        raise MarketDataError(
            f"Failed to fetch market data for {symbol}: {exc}"
        ) from exc

    if history is None or history.empty:
        raise MarketDataError(f"No market data returned for {symbol}.")

    required_columns = ["Open", "High", "Low", "Close", "Volume"]
    missing_columns = [column for column in required_columns if column not in history.columns]
    if missing_columns:
        raise MarketDataError(
            f"Missing required columns for {symbol}: {missing_columns}"
        )

    close_values = _series_to_float_list(history["Close"])
    if not close_values:
        raise MarketDataError(f"No closing prices available for {symbol}.")

    dates = [index.strftime("%Y-%m-%d") for index in history.index.to_pydatetime()]

    return {
        "ticker": symbol,
        "dates": dates,
        "open": _series_to_float_list(history["Open"]),
        "high": _series_to_float_list(history["High"]),
        "low": _series_to_float_list(history["Low"]),
        "close": close_values,
        "volume": _series_to_float_list(history["Volume"]),
    }