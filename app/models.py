


from dataclasses import dataclass
from typing import List, Optional, Dict, Any


# =========================
# NEWS
# =========================
@dataclass
class NewsArticle:
    title: str
    summary: str
    source: str
    published_at: Optional[str] = None


# =========================
# ENRICHED NEWS (LLM OUTPUT)
# =========================
@dataclass
class EnrichedArticle:
    title: str
    summary: str
    source: str

    sentiment: str
    impact_score: int
    theme: str
    assets: List[str]

    raw: Optional[Dict[str, Any]] = None


# =========================
# TECHNICALS
# =========================
@dataclass
class TechnicalData:
    ticker: str
    rsi: float
    macd: float
    macd_signal: float
    technical_bias: str
    technical_reason: str


# =========================
# SIGNAL
# =========================
@dataclass
class Signal:
    action: str
    assets: List[str]
    confidence: int
    reason: str

    technicals: Optional[TechnicalData] = None


# =========================
# FINAL PIPELINE OUTPUT
# =========================
@dataclass
class SignalResult:
    title: str
    signal: Signal