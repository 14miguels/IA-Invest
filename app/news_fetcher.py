from typing import List, Dict, Any, Set

import feedparser

from app.config import RSS_FEEDS, MAX_NEWS_PER_FEED
from app.news_cleaner import clean_article, is_valid_article


USER_AGENT = "InvestBot/1.0 (+https://example.com)"


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def fetch_news() -> List[Dict[str, Any]]:
    """
    Fetch and clean news from configured RSS feeds.

    - Limits articles per feed
    - Deduplicates by (title, url)
    - Handles feed errors gracefully
    """
    articles: List[Dict[str, Any]] = []
    seen: Set[tuple[str, str]] = set()

    for feed in RSS_FEEDS:
        try:
            parsed = feedparser.parse(
                feed["url"],
                request_headers={"User-Agent": USER_AGENT},
            )
        except Exception:
            # Skip broken feeds
            continue

        entries = getattr(parsed, "entries", [])[:MAX_NEWS_PER_FEED]

        for entry in entries:
            title = _safe_str(entry.get("title"))
            url = _safe_str(entry.get("link"))

            if not title or not url:
                continue

            # Dedup
            key = (title, url)
            if key in seen:
                continue
            seen.add(key)

            raw_article = {
                "title": title,
                "source": _safe_str(feed.get("name")),
                "url": url,
                "published_at": _safe_str(entry.get("published")),
                "summary": _safe_str(entry.get("summary") or entry.get("description")),
                "raw_text": _safe_str(entry.get("summary") or entry.get("description")),
            }

            try:
                cleaned = clean_article(raw_article)
            except Exception:
                continue

            if is_valid_article(cleaned):
                articles.append(cleaned)

    return articles
