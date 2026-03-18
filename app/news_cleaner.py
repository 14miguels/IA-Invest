import html
import re
from typing import Any, Dict


TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")

MIN_TITLE_LEN = 10
MIN_SUMMARY_LEN = 30
MAX_TITLE_LEN = 300
MAX_SUMMARY_LEN = 2000


def strip_html(text: str) -> str:
    """Remove HTML tags and unescape HTML entities."""
    if not text:
        return ""

    no_tags = TAG_RE.sub(" ", text)
    unescaped = html.unescape(no_tags)
    return WHITESPACE_RE.sub(" ", unescaped).strip()


def normalize_text(text: str) -> str:
    """Normalize free text for storage and downstream processing."""
    cleaned = strip_html(text)
    cleaned = cleaned.replace("\x00", "").strip()
    return cleaned


def clean_article(article: Dict[str, Any]) -> Dict[str, Any]:
    """Return a cleaned copy of an RSS article dictionary."""
    title = normalize_text(str(article.get("title") or ""))[:MAX_TITLE_LEN]
    summary = normalize_text(str(article.get("summary") or ""))[:MAX_SUMMARY_LEN]
    raw_text = normalize_text(str(article.get("raw_text") or summary))[:MAX_SUMMARY_LEN]
    source = normalize_text(str(article.get("source") or "Unknown"))
    url = str(article.get("url") or "").strip()
    published_at = str(article.get("published_at") or "").strip()

    # Basic URL sanity
    if url and not (url.startswith("http://") or url.startswith("https://")):
        url = ""

    return {
        "title": title,
        "source": source,
        "url": url,
        "published_at": published_at,
        "summary": summary,
        "raw_text": raw_text,
    }


def is_valid_article(article: Dict[str, Any]) -> bool:
    """Basic validation so we only store usable articles."""
    title = str(article.get("title") or "")
    summary = str(article.get("summary") or "")
    url = str(article.get("url") or "")

    if not title or len(title) < MIN_TITLE_LEN:
        return False

    if not url:
        return False

    # Ensure we have some meaningful content
    if len(summary) < MIN_SUMMARY_LEN:
        return False

    return True