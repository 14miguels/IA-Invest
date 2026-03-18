

from app.llm_classifier import classify_news


def test_llm_classifier_basic():
    """Basic test to ensure classifier returns expected structure."""

    article = {
        "title": "Nvidia shares surge as AI demand grows",
        "summary": "Investors expect strong datacenter revenue.",
        "source": "Reuters",
    }

    result = classify_news(article)

    assert isinstance(result, dict)

    # Required fields
    assert "sentiment" in result
    assert "impact_score" in result
    assert "theme" in result
    assert "assets" in result

    assert result["sentiment"] in ["positive", "neutral", "negative"]
    assert isinstance(result["impact_score"], int)
    assert isinstance(result["assets"], list)

    print("LLM classifier basic test passed ✔")


def test_llm_classifier_multiple_inputs():
    """Test classifier on multiple articles."""

    articles = [
        {
            "title": "Oil prices surge amid geopolitical tensions",
            "summary": "Middle East conflict pushes oil higher.",
            "source": "Reuters",
        },
        {
            "title": "Tech stocks fall as rates rise",
            "summary": "Higher interest rates pressure valuations.",
            "source": "Bloomberg",
        },
    ]

    for article in articles:
        result = classify_news(article)
        assert isinstance(result, dict)
        assert "sentiment" in result
        assert "impact_score" in result

    print("LLM classifier multiple test passed ✔")


if __name__ == "__main__":
    test_llm_classifier_basic()
    test_llm_classifier_multiple_inputs()