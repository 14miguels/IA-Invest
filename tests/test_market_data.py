

from app.market_data import get_price_history


def test_get_price_history_basic():
    """Ensure we can fetch price history and structure is correct."""

    data = get_price_history("NVDA")

    assert isinstance(data, dict)
    assert "close" in data

    closes = data["close"]
    assert isinstance(closes, list)
    assert len(closes) > 0

    # Values should be floats
    assert isinstance(closes[0], float)

    print("Market data basic test passed ✔")


def test_get_price_history_multiple_assets():
    """Test multiple tickers don't break the fetcher."""

    tickers = ["NVDA", "AAPL", "MSFT"]

    for ticker in tickers:
        data = get_price_history(ticker)
        assert "close" in data
        assert len(data["close"]) > 0

    print("Market data multiple test passed ✔")


if __name__ == "__main__":
    test_get_price_history_basic()
    test_get_price_history_multiple_assets()