


from app.signal_engine import generate_signal, generate_signals


def test_generate_signal_basic():
    """Test single signal generation."""

    article = {
        "title": "Nvidia shares surge as AI demand grows",
        "theme": "tech",
        "sentiment": "positive",
        "impact_score": 4,
        "assets": ["NVDA"],
    }

    result = generate_signal(article)

    assert isinstance(result, dict)
    assert "action" in result
    assert "confidence" in result
    assert "reason" in result
    assert "technicals" in result

    assert result["action"] in ["BUY", "HOLD", "SELL"]
    assert isinstance(result["confidence"], int)

    print("Signal engine basic test passed ✔")


def test_generate_signal_no_assets():
    """Signal generation should handle missing assets."""

    article = {
        "title": "Macro uncertainty rises",
        "theme": "macro",
        "sentiment": "neutral",
        "impact_score": 2,
        "assets": [],
    }

    result = generate_signal(article)

    assert result["action"] in ["BUY", "HOLD", "SELL"]

    print("Signal engine no-assets test passed ✔")


def test_generate_signals_batch():
    """Test batch signal generation."""

    articles = [
        {
            "title": "Nvidia shares surge as AI demand grows",
            "theme": "tech",
            "sentiment": "positive",
            "impact_score": 4,
            "assets": ["NVDA"],
        },
        {
            "title": "Oil prices surge amid geopolitical tensions",
            "theme": "energy",
            "sentiment": "positive",
            "impact_score": 5,
            "assets": ["OIL"],
        },
    ]

    results = generate_signals(articles)

    assert isinstance(results, list)
    assert len(results) == 2

    for entry in results:
        assert "title" in entry
        assert "signal" in entry

    print("Signal engine batch test passed ✔")


if __name__ == "__main__":
    test_generate_signal_basic()
    test_generate_signal_no_assets()
    test_generate_signals_batch()