from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List

from app.gemini_client import GeminiClientError, classify_with_gemini

LLM_AVAILABLE = True


# Simple in-memory cache to avoid duplicate LLM calls
_CACHE_LOCK = threading.Lock()
_CLASSIFICATION_CACHE: Dict[str, Dict[str, Any]] = {}


TECH_KEYWORDS = {
    "ai",
    "artificial intelligence",
    "nvidia",
    "semiconductor",
    "chip",
    "chips",
    "microsoft",
    "meta",
    "google",
    "amazon",
    "tesla",
    "apple",
    "openai",
    "datacenter",
    "cloud",
}

DEFENSE_KEYWORDS = {
    "war",
    "missile",
    "attack",
    "military",
    "defense",
    "defence",
    "drone",
    "weapons",
    "airstrike",
    "troops",
    "conflict",
    "security",
}

GOLD_KEYWORDS = {
    "gold",
    "safe haven",
    "bullion",
    "precious metal",
    "hedge",
}

OIL_KEYWORDS = {
    "oil",
    "crude",
    "brent",
    "wti",
    "opec",
    "barrel",
    "energy supply",
}

RATES_KEYWORDS = {
    "inflation",
    "interest rate",
    "interest rates",
    "fed",
    "ecb",
    "central bank",
    "rate cut",
    "rate hike",
    "bond yield",
    "yields",
    "cpi",
}

POSITIVE_KEYWORDS = {
    "surge",
    "gain",
    "gains",
    "jump",
    "jumps",
    "beat",
    "beats",
    "growth",
    "record",
    "strong",
    "bullish",
    "rise",
    "rises",
    "rally",
}

NEGATIVE_KEYWORDS = {
    "fall",
    "falls",
    "drop",
    "drops",
    "slump",
    "warns",
    "warning",
    "cuts",
    "cut",
    "miss",
    "misses",
    "weak",
    "bearish",
    "attack",
    "crisis",
    "risk",
}

ASSET_KEYWORDS = {
    "nvidia": "NVDA",
    "microsoft": "MSFT",
    "meta": "META",
    "apple": "AAPL",
    "amazon": "AMZN",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "tesla": "TSLA",
    "qqq": "QQQ",
    "nasdaq": "QQQ",
    "s&p 500": "VOO",
    "sp500": "VOO",
    "voo": "VOO",
    "raytheon": "RTX",
    "rtx": "RTX",
    "lockheed": "LMT",
    "gold": "GOLD",
    "bullion": "GOLD",
    "oil": "OIL",
    "brent": "OIL",
    "crude": "OIL",
}


def _normalize_text(article: Dict[str, Any]) -> str:
    title = str(article.get("title") or "")
    summary = str(article.get("summary") or "")
    source = str(article.get("source") or "")
    return f"{title} {summary} {source}".lower().strip()



def _cache_key(article: Dict[str, Any]) -> str:
    title = str(article.get("title") or "")
    summary = str(article.get("summary") or "")
    return f"{title}::{summary}".lower().strip()



def _get_cached_result(cache_key: str) -> Dict[str, Any] | None:
    with _CACHE_LOCK:
        cached = _CLASSIFICATION_CACHE.get(cache_key)
        return dict(cached) if cached is not None else None



def _store_cached_result(cache_key: str, result: Dict[str, Any]) -> None:
    with _CACHE_LOCK:
        _CLASSIFICATION_CACHE[cache_key] = dict(result)



def detect_theme(text: str) -> str:
    """Detect the main theme of a news item using simple keyword rules."""
    if any(keyword in text for keyword in DEFENSE_KEYWORDS):
        return "defense"
    if any(keyword in text for keyword in TECH_KEYWORDS):
        return "tech"
    if any(keyword in text for keyword in GOLD_KEYWORDS):
        return "gold"
    if any(keyword in text for keyword in OIL_KEYWORDS):
        return "oil"
    if any(keyword in text for keyword in RATES_KEYWORDS):
        return "rates"
    return "macro"



def detect_sentiment(text: str) -> str:
    """Detect basic sentiment from headline/summary text."""
    positive_hits = sum(1 for keyword in POSITIVE_KEYWORDS if keyword in text)
    negative_hits = sum(1 for keyword in NEGATIVE_KEYWORDS if keyword in text)

    if positive_hits > negative_hits:
        return "positive"
    if negative_hits > positive_hits:
        return "negative"
    return "neutral"



def detect_assets(text: str, theme: str) -> List[str]:
    """Infer related assets/tickers from text and theme."""
    assets: List[str] = []

    for keyword, ticker in ASSET_KEYWORDS.items():
        if keyword in text and ticker not in assets:
            assets.append(ticker)

    if not assets:
        if theme == "tech":
            assets.extend(["QQQ", "NVDA"])
        elif theme == "defense":
            assets.extend(["RTX", "LMT"])
        elif theme == "gold":
            assets.append("GOLD")
        elif theme == "oil":
            assets.append("OIL")
        elif theme == "rates":
            assets.extend(["VOO", "QQQ"])

    return assets



def detect_impact_score(text: str, sentiment: str, theme: str) -> int:
    """Assign a simple 1-5 impact score based on theme and urgency keywords."""
    high_impact_words = {
        "breaking",
        "urgent",
        "attack",
        "war",
        "crisis",
        "record",
        "surge",
        "slump",
        "rate hike",
        "rate cut",
    }

    score = 2

    if theme in {"defense", "rates", "oil", "tech"}:
        score += 1

    if sentiment in {"positive", "negative"}:
        score += 1

    if any(word in text for word in high_impact_words):
        score += 1

    return min(score, 5)



def build_short_reason(theme: str, sentiment: str, assets: List[str]) -> str:
    """Create a short explanation for downstream signals."""
    asset_text = ", ".join(assets) if assets else "broad markets"
    return (
        f"Classified as {sentiment} {theme} news with likely relevance for {asset_text}."
    )



def classify_news_rules(article: Dict[str, Any]) -> Dict[str, Any]:
    """Classify a news article using the local keyword-based fallback rules."""
    combined_text = _normalize_text(article)

    theme = detect_theme(combined_text)
    sentiment = detect_sentiment(combined_text)
    assets = detect_assets(combined_text, theme)
    impact_score = detect_impact_score(combined_text, sentiment, theme)
    short_reason = build_short_reason(theme, sentiment, assets)

    return {
        "sentiment": sentiment,
        "theme": theme,
        "assets": assets,
        "impact_score": impact_score,
        "short_reason": short_reason,
    }



def classify_news(article: Dict[str, Any]) -> Dict[str, Any]:
    global LLM_AVAILABLE

    cache_key = _cache_key(article)
    cached = _get_cached_result(cache_key)
    if cached is not None:
        return cached

    if not LLM_AVAILABLE:
        result = classify_news_rules(article)
        _store_cached_result(cache_key, result)
        return result

    try:
        print("[LLM] Using Gemini classification")
        result = classify_with_gemini(article)
    except GeminiClientError as exc:
        print(f"[FALLBACK] Disabling Gemini for this run: {exc}")
        LLM_AVAILABLE = False
        result = classify_news_rules(article)

    _store_cached_result(cache_key, result)
    return result



def classify_news_batch(
    articles: List[Dict[str, Any]],
    max_workers: int = 5,
) -> List[Dict[str, Any]]:
    """Parallel classification of news articles using threads and deduped cache keys."""
    if not articles:
        return []

    results: List[Dict[str, Any] | None] = [None] * len(articles)
    grouped_indices: Dict[str, List[int]] = {}

    for idx, article in enumerate(articles):
        key = _cache_key(article)
        grouped_indices.setdefault(key, []).append(idx)

    unique_articles: List[tuple[str, Dict[str, Any]]] = []
    for key, indices in grouped_indices.items():
        cached = _get_cached_result(key)
        if cached is not None:
            for idx in indices:
                results[idx] = cached
        else:
            unique_articles.append((key, articles[indices[0]]))

    if unique_articles:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_key = {
                executor.submit(classify_news, article): key
                for key, article in unique_articles
            }

            resolved_results: Dict[str, Dict[str, Any]] = {}
            for future in as_completed(future_to_key):
                key = future_to_key[future]
                resolved_results[key] = future.result()

        for key, indices in grouped_indices.items():
            resolved = results[indices[0]] if results[indices[0]] is not None else resolved_results.get(key)
            if resolved is None:
                resolved = classify_news_rules(articles[indices[0]])
            for idx in indices:
                results[idx] = dict(resolved)

    return [result or classify_news_rules(article) for result, article in zip(results, articles)]