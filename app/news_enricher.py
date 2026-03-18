from typing import Any

from app.llm_classifier import classify_news, classify_news_batch
from app.models import EnrichedArticle


def enrich_article(article: dict[str, Any]) -> EnrichedArticle:
    """
    Enrich a news article with classification data.

    Takes a raw/clean article dict and returns an EnrichedArticle.
    """
    classification = classify_news(article)

    return EnrichedArticle(
        title=str(article.get("title") or ""),
        summary=str(article.get("summary") or ""),
        source=str(article.get("source") or ""),
        sentiment=str(classification["sentiment"]),
        impact_score=int(classification["impact_score"]),
        theme=str(classification["theme"]),
        assets=[str(asset) for asset in classification.get("assets", [])],
        raw={
            **article,
            "short_reason": classification.get("short_reason"),
        },
    )


def enrich_articles(articles: list[dict[str, Any]]) -> list[EnrichedArticle]:
    """Enrich a list of articles using batched LLM classification."""
    if not articles:
        return []

    # Batch classify (parallel + cached)
    classifications = classify_news_batch(articles)

    enriched: list[EnrichedArticle] = []

    # Zip original articles with their classifications
    for article, classification in zip(articles, classifications):
        enriched.append(
            EnrichedArticle(
                title=str(article.get("title") or ""),
                summary=str(article.get("summary") or ""),
                source=str(article.get("source") or ""),
                sentiment=str(classification.get("sentiment", "neutral")),
                impact_score=int(classification.get("impact_score", 1)),
                theme=str(classification.get("theme", "")),
                assets=[str(asset) for asset in classification.get("assets", [])],
                raw={
                    **article,
                    "short_reason": classification.get("short_reason"),
                },
            )
        )

    return enriched
