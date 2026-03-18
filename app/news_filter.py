from typing import Any, Dict, List


TRADABLE_THEMES = {"tech", "defense", "oil", "gold", "rates", "macro"}

# Strong negative filters: content that is usually not actionable for a trading pipeline.
NON_TRADABLE_KEYWORDS = {
    "march madness",
    "vacation debt",
    "second home",
    "retirement",
    "credit card",
    "personal finance",
    "your bracket",
    "what could go wrong",
    "how to",
    "should i",
    "advice",
    "tips",
    "mortgage calculator",
    "debt payoff",
    "budgeting",
    "lifestyle",
    "celebrity",
    "cba deal",
    "horoscope",
    "dating",
    "wedding",
    "travel tips",
    "gift guide",
    "shopping guide",
    "recipe",
    "health tips",
    "fitness tips",
    "coupon",
    "lottery",
}

# Soft negative filters: often low-signal unless the article is strongly market-linked.
LOW_SIGNAL_KEYWORDS = {
    "opinion",
    "editorial",
    "analysis",
    "newsletter",
    "explainer",
    "what to know",
    "what to expect",
    "what happened",
    "what it means",
    "hearing wednesday",
    "new chapter",
    "takes over as ceo",
    "players' union",
    "landmark deal",
}

# Strong positive filters for market relevance.
TRADABLE_KEYWORDS = {
    "fed",
    "federal reserve",
    "interest rates",
    "inflation",
    "cpi",
    "ppi",
    "jobs report",
    "payrolls",
    "yield",
    "yields",
    "bond",
    "treasury",
    "rate cut",
    "rate hike",
    "hawkish",
    "dovish",
    "oil",
    "crude",
    "brent",
    "wti",
    "gold",
    "bullion",
    "commodity",
    "commodities",
    "aluminum",
    "aluminium",
    "copper",
    "supply disruption",
    "shipping",
    "strait of hormuz",
    "sanctions",
    "war",
    "conflict",
    "attack",
    "missile",
    "airstrike",
    "nvidia",
    "nvda",
    "tesla",
    "apple",
    "microsoft",
    "amazon",
    "meta",
    "google",
    "alphabet",
    "amd",
    "tsm",
    "micron",
    "semiconductor",
    "chips",
    "datacenter",
    "ai",
    "artificial intelligence",
    "earnings",
    "guidance",
    "forecast",
    "revenue",
    "margin",
    "profit",
    "loss",
    "beat",
    "beats",
    "miss",
    "misses",
    "upgrade",
    "downgrade",
    "buyback",
    "merger",
    "acquisition",
    "ipo",
}

# Extra boost for explicitly market-moving company/event language.
HIGH_SIGNAL_KEYWORDS = {
    "earnings",
    "guidance",
    "forecast",
    "revenue",
    "margin",
    "profit",
    "loss",
    "beat",
    "beats",
    "miss",
    "misses",
    "rate cut",
    "rate hike",
    "inflation",
    "jobs report",
    "war",
    "sanctions",
    "supply disruption",
    "shipping",
    "strait of hormuz",
    "surge",
    "slump",
    "record",
    "warning",
    "downgrade",
    "upgrade",
}

# Recognized market assets/tickers/benchmarks. Presence usually means the article is tradable.
KNOWN_ASSETS = {
    "NVDA",
    "AMD",
    "TSM",
    "MU",
    "AAPL",
    "MSFT",
    "AMZN",
    "META",
    "GOOGL",
    "TSLA",
    "QQQ",
    "VOO",
    "SPY",
    "DIA",
    "RTX",
    "LMT",
    "NOC",
    "GOLD",
    "GLD",
    "OIL",
    "USO",
}

MIN_TITLE_LENGTH = 12
MIN_SUMMARY_LENGTH = 20
MIN_TRADABLE_SCORE = 2


COMPANY_EVENT_KEYWORDS = {
    "earnings",
    "guidance",
    "forecast",
    "revenue",
    "margin",
    "profit",
    "loss",
    "beat",
    "beats",
    "miss",
    "misses",
    "upgrade",
    "downgrade",
    "buyback",
    "acquisition",
    "merger",
    "ipo",
    "shares surge",
    "shares fall",
}


def _combined_text(article: Dict[str, Any]) -> str:
    title = str(article.get("title") or "")
    summary = str(article.get("summary") or "")
    source = str(article.get("source") or "")
    return f"{title} {summary} {source}".lower().strip()


def _contains_any(text: str, keywords: set[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _normalized_assets(article: Dict[str, Any]) -> List[str]:
    assets = article.get("assets") or []
    if not isinstance(assets, list):
        return []
    return [str(asset).upper().strip() for asset in assets if str(asset).strip()]


def _is_low_quality(article: Dict[str, Any]) -> bool:
    title = str(article.get("title") or "").strip()
    summary = str(article.get("summary") or "").strip()

    if len(title) < MIN_TITLE_LENGTH:
        return True

    if summary and len(summary) < MIN_SUMMARY_LENGTH:
        return True

    return False


def _looks_like_soft_company_news(text: str, assets: List[str]) -> bool:
    has_company_asset = any(asset in KNOWN_ASSETS for asset in assets)
    has_hard_company_event = _contains_any(text, COMPANY_EVENT_KEYWORDS)
    has_soft_company_language = _contains_any(text, LOW_SIGNAL_KEYWORDS)

    return has_company_asset and has_soft_company_language and not has_hard_company_event


def _tradable_score(article: Dict[str, Any]) -> int:
    text = _combined_text(article)
    theme = str(article.get("theme") or "").lower().strip()
    assets = _normalized_assets(article)

    score = 0

    if theme in TRADABLE_THEMES:
        score += 2

    if _contains_any(text, TRADABLE_KEYWORDS):
        score += 2

    if _contains_any(text, HIGH_SIGNAL_KEYWORDS):
        score += 2

    recognized_assets = [asset for asset in assets if asset in KNOWN_ASSETS]
    if recognized_assets:
        score += 2
        if len(recognized_assets) >= 2:
            score += 1

    # Penalties
    if _contains_any(text, LOW_SIGNAL_KEYWORDS):
        score -= 1

    return score


def is_tradable_article(article: Dict[str, Any]) -> bool:
    """Return True if the article is relevant for market/trading decisions."""
    text = _combined_text(article)
    assets = _normalized_assets(article)

    if _is_low_quality(article):
        return False

    if _contains_any(text, NON_TRADABLE_KEYWORDS):
        return False

    if _looks_like_soft_company_news(text, assets):
        return False

    return _tradable_score(article) >= MIN_TRADABLE_SCORE


def filter_tradable_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter a list of articles, keeping only tradable/market-relevant ones."""
    return [article for article in articles if is_tradable_article(article)]
