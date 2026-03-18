from app.market_data import get_price_history
from app.technical_analyzer import analyze_technicals


def test_analyze_technicals_basic():
    """Ensure technical analysis returns expected structure."""

    data = get_price_history("NVDA")
    result = analyze_technicals(data)

    assert isinstance(result, dict)

    # Required fields
    assert "ticker" in result
    assert "rsi" in result
    assert "macd" in result
    assert "macd_signal" in result
    assert "technical_bias" in result
    assert "technical_reason" in result

    assert result["technical_bias"] in ["bullish", "neutral", "bearish"]

    print("Technical analyzer basic test passed ✔")


def test_analyze_technicals_values():
    """Check RSI and MACD ranges are reasonable."""

    data = get_price_history("AAPL")
    result = analyze_technicals(data)

    rsi = result["rsi"]
    macd = result["macd"]

    assert isinstance(rsi, float)
    assert 0 <= rsi <= 100

    assert isinstance(macd, float)

    print("Technical analyzer values test passed ✔")


def test_analyze_technicals_multiple_assets():
    """Run analyzer on multiple tickers to ensure stability."""

    tickers = ["NVDA", "MSFT", "TSLA"]

    for ticker in tickers:
        data = get_price_history(ticker)
        result = analyze_technicals(data)

        assert "technical_bias" in result

    print("Technical analyzer multiple test passed ✔")


if __name__ == "__main__":
    test_analyze_technicals_basic()
    test_analyze_technicals_values()
    test_analyze_technicals_multiple_assets()
