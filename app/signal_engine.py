from typing import Any, Dict, List

from app.market_data import MarketDataError, get_price_history
from app.models import EnrichedArticle
from app.technical_analyzer import TechnicalAnalysisError, analyze_technicals
from app.utils import unique_preserve_order


DEFAULT_TECHNICAL_BY_ASSET = {
    "NVDA": "NVDA",
    "QQQ": "QQQ",
    "VOO": "VOO",
    "TSLA": "TSLA",
    "AAPL": "AAPL",
    "MSFT": "MSFT",
    "AMZN": "AMZN",
    "META": "META",
    "GOOGL": "GOOGL",
    "DIS": "DIS",
    "AMD": "AMD",
    "TSM": "TSM",
    "MU": "MU",
    "RTX": "RTX",
    "LMT": "LMT",
    "NOC": "NOC",
    "GLD": "GLD",
    "GOLD": "GLD",
    "USO": "USO",
    "OIL": "USO",
}

TECH_FRIENDLY_THEMES = {"tech", "defense", "gold", "oil", "rates"}
TRADABLE_EVENT_TYPES = {
    "geopolitical_supply_shock",
    "geopolitical_defense",
    "rates_hawkish",
    "rates_dovish",
    "oil_market_stabilization",
    "company_earnings_positive",
    "company_earnings_negative",
    "ai_momentum",
    "speculative_spike",
    "commodity_supply_disruption",
    "safe_haven_risk_off",
}

SPECULATIVE_SPIKE_KEYWORDS = {
    "surges 1,100%",
    "soars 500%",
    "surges 500%",
    "fervent demand",
    "parabolic",
    "meme stock",
}

GEOPOLITICAL_SUPPLY_SHOCK_KEYWORDS = {
    "strait of hormuz",
    "hormuz",
    "blockade",
    "chokes supply",
    "supply disruption",
    "supply disruptions",
    "supply risk",
    "sanctions",
    "export disruption",
    "oil prices surge",
    "crude surges",
    "retaliatory strike",
    "missile strikes",
    "missile strike",
}

DEFENSE_ESCALATION_KEYWORDS = {
    "war",
    "attack",
    "attacks",
    "airstrike",
    "airstrikes",
    "missile",
    "missiles",
    "drone",
    "drones",
    "retaliatory",
    "retaliation",
    "troops",
    "military",
    "defense",
    "defence",
    "conflict",
    "security",
    "assassination",
    "killed",
    "killing",
}

RATES_HAWKISH_KEYWORDS = {
    "rate hike",
    "rate hikes",
    "higher rates",
    "rates rise",
    "rising rates",
    "hawkish",
    "higher yields",
    "inflation uptick",
    "sticky inflation",
    "hot inflation",
    "rate cut gets pushed back",
    "cuts get pushed back",
    "pushed back after hot inflation",
    "higher for longer",
}

RATES_DOVISH_KEYWORDS = {
    "rate cut",
    "rate cuts",
    "cut rates",
    "cuts rates",
    "easing",
    "falling rates",
    "lower yields",
    "softer inflation",
    "disinflation",
}

EARNINGS_POSITIVE_KEYWORDS = {
    "beats",
    "beat",
    "guidance raised",
    "raises guidance",
    "strong revenue",
    "record revenue",
    "margin expansion",
    "profit jumps",
    "surges after earnings",
}

EARNINGS_NEGATIVE_KEYWORDS = {
    "misses",
    "miss",
    "cuts guidance",
    "guidance cut",
    "weak demand",
    "margin pressure",
    "revenue miss",
    "profit warning",
    "shares fall after earnings",
}

AI_MOMENTUM_KEYWORDS = {
    "ai",
    "artificial intelligence",
    "datacenter",
    "chip demand",
    "strong ai demand",
    "next chatgpt",
    "model demand",
    "semiconductor",
    "chips",
    "gpu",
}

COMMODITY_SUPPLY_DISRUPTION_KEYWORDS = {
    "aluminum prices surged",
    "aluminium prices surged",
    "commodity shortage",
    "commodities strategy",
    "supply shortage",
    "mine disruption",
    "metal prices surge",
    "chokes supply",
}

SAFE_HAVEN_KEYWORDS = {
    "safe haven",
    "risk-off",
    "flight to safety",
    "geopolitical tensions",
    "escalation",
    "uncertainty",
}
STEADY_OIL_MARKET_KEYWORDS = {
    "steady oil market",
    "stabilize oil market",
    "stabilise oil market",
    "steady the oil market",
    "ease oil market",
    "calm oil market",
    "waives u.s. shipping law",
    "waives shipping law",
    "waives jones act",
    "jones act waiver",
}

NON_TRADABLE_COMPANY_KEYWORDS = {
    "new chapter",
    "takes over as ceo",
    "hearing wednesday",
    "players' union",
    "cba deal",
    "march madness",
    "vacation debt",
    "retirement",
    "second home",
    "credit card",
}



def _safe_assets(article: Dict[str, Any] | EnrichedArticle) -> List[str]:
    if isinstance(article, dict):
        assets = article.get("assets", [])
    else:
        assets = getattr(article, "assets", [])

    if not isinstance(assets, list):
        return []

    return unique_preserve_order((str(asset).upper() for asset in assets if asset), upper=True)



def _get_field(article: Dict[str, Any] | EnrichedArticle, field: str, default=None):
    if isinstance(article, dict):
        return article.get(field, default)
    return getattr(article, field, default)



def _combined_text(article: Dict[str, Any] | EnrichedArticle) -> str:
    title = str(_get_field(article, "title", "") or "")
    summary = str(_get_field(article, "summary", "") or "")

    raw = _get_field(article, "raw", None)
    short_reason = ""
    if isinstance(raw, dict):
        short_reason = str(raw.get("short_reason") or "")

    return f"{title} {summary} {short_reason}".lower()



def _contains_any(text: str, keywords: set[str]) -> bool:
    return any(keyword in text for keyword in keywords)



def _detect_event_type(article: Dict[str, Any] | EnrichedArticle, theme: str, assets: List[str]) -> str:
    text = _combined_text(article)

    if (
        "ALUMINUM" in assets
        or "aluminum" in text
        or "aluminium" in text
    ) and _contains_any(text, COMMODITY_SUPPLY_DISRUPTION_KEYWORDS):
        return "commodity_supply_disruption"

    if theme == "defense" and _contains_any(text, DEFENSE_ESCALATION_KEYWORDS):
        if any(token in text for token in {"hormuz", "shipping", "blockade", "sanctions", "chokes supply", "supply disruption"}):
            return "geopolitical_supply_shock"
        return "geopolitical_defense"

    if _contains_any(text, GEOPOLITICAL_SUPPLY_SHOCK_KEYWORDS):
        return "geopolitical_supply_shock"
    
    if _contains_any(text, SPECULATIVE_SPIKE_KEYWORDS):
        return "speculative_spike"
    
    if theme == "rates" and _contains_any(text, RATES_HAWKISH_KEYWORDS):
        return "rates_hawkish"

    if theme == "rates" and _contains_any(text, RATES_DOVISH_KEYWORDS):
        return "rates_dovish"

    if _contains_any(text, NON_TRADABLE_COMPANY_KEYWORDS):
        return "non_tradable"

    if any(asset in {"NVDA", "AMD", "TSM", "MU", "QQQ", "AAPL", "MSFT", "AMZN", "META", "GOOGL"} for asset in assets):
        if _contains_any(text, EARNINGS_POSITIVE_KEYWORDS):
            return "company_earnings_positive"
        if _contains_any(text, EARNINGS_NEGATIVE_KEYWORDS):
            return "company_earnings_negative"
        if theme == "tech" and _contains_any(text, AI_MOMENTUM_KEYWORDS):
            return "ai_momentum"

    if theme == "oil" and _contains_any(text, GEOPOLITICAL_SUPPLY_SHOCK_KEYWORDS):
        return "geopolitical_supply_shock"
    
    if theme == "oil" and _contains_any(text, STEADY_OIL_MARKET_KEYWORDS):
        return "oil_market_stabilization"

    if (theme in {"oil", "macro"} or any(asset in {"OIL", "USO", "GOLD", "GLD"} for asset in assets)) and _contains_any(text, SAFE_HAVEN_KEYWORDS):
        return "safe_haven_risk_off"

    if _contains_any(text, COMMODITY_SUPPLY_DISRUPTION_KEYWORDS):
        return "commodity_supply_disruption"

    return "theme_fallback"



def _pick_technical_ticker(theme: str, assets: List[str]) -> str | None:
    for asset in assets:
        mapped = DEFAULT_TECHNICAL_BY_ASSET.get(asset)
        if mapped:
            return mapped

    theme_defaults = {
        "tech": "QQQ",
        "defense": "RTX",
        "gold": "GLD",
        "oil": "USO",
        "rates": "VOO",
    }
    return theme_defaults.get(theme)



def _get_technical_context(theme: str, assets: List[str]) -> Dict[str, Any] | None:
    if theme not in TECH_FRIENDLY_THEMES:
        return None

    ticker = _pick_technical_ticker(theme, assets)
    if not ticker:
        return None

    try:
        price_data = get_price_history(ticker)
        return analyze_technicals(price_data)
    except (MarketDataError, TechnicalAnalysisError):
        return None



def _adjust_confidence(base_confidence: int, technical_bias: str, action: str) -> int:
    confidence = base_confidence

    if action == "BUY" and technical_bias == "bullish":
        confidence += 1
    elif action == "SELL" and technical_bias == "bearish":
        confidence += 1
    elif action == "BUY" and technical_bias == "bearish":
        confidence -= 1
    elif action == "SELL" and technical_bias == "bullish":
        confidence -= 1

    return max(1, min(confidence, 5))



def _merge_reason(base_reason: str, technicals: Dict[str, Any] | None) -> str:
    if not technicals:
        return base_reason

    technical_reason = technicals.get("technical_reason")
    technical_bias = technicals.get("technical_bias")
    if not technical_reason or not technical_bias:
        return base_reason

    return f"{base_reason} Technicals are {technical_bias}: {technical_reason}"



def _normalize_assets(theme: str, assets: List[str]) -> List[str]:
    if assets:
        return unique_preserve_order(assets, upper=True)

    defaults = {
        "tech": ["QQQ"],
        "defense": ["RTX", "LMT"],
        "gold": ["GOLD"],
        "oil": ["OIL"],
        "rates": ["VOO"],
    }
    return defaults.get(theme, [])



def _build_signal_from_event(
    event_type: str,
    article: Dict[str, Any] | EnrichedArticle,
    theme: str,
    sentiment: str,
    impact: int,
    assets: List[str],
) -> Dict[str, Any]:
    resolved_assets = _normalize_assets(theme, assets)
    action = "HOLD"
    confidence = 1
    reason = "No strong signal."

    if event_type == "geopolitical_supply_shock":
        action = "BUY"
        confidence = max(impact, 4)
        resolved_assets = ["OIL"]
        reason = "Supply disruption risk may push oil and energy prices higher."

    elif event_type == "geopolitical_defense":
        action = "BUY"
        confidence = max(impact, 4)
        resolved_assets = ["RTX", "LMT"]
        reason = "Military escalation may increase defense spending and contractor demand."

    elif event_type == "rates_hawkish":
        action = "SELL"
        confidence = max(impact, 4)
        resolved_assets = unique_preserve_order(resolved_assets or ["VOO", "QQQ"], upper=True)
        reason = "Higher rates and yields may pressure equity valuations."

    elif event_type == "oil_market_stabilization":
        action = "HOLD"
        confidence = max(impact - 1, 2)
        resolved_assets = unique_preserve_order(resolved_assets + ["OIL"], upper=True)
        reason = "Policy action may stabilize the oil market, reducing directional conviction."

    elif event_type == "rates_dovish":
        action = "BUY"
        confidence = max(impact, 4)
        resolved_assets = unique_preserve_order(resolved_assets or ["VOO", "QQQ"], upper=True)
        reason = "Rate cuts or easing may support equity multiples."

    elif event_type == "company_earnings_positive":
        action = "BUY"
        confidence = max(impact, 4)
        reason = "Positive earnings or guidance may support the stock."

    elif event_type == "company_earnings_negative":
        action = "SELL"
        confidence = max(impact, 4)
        reason = "Negative earnings or guidance may pressure the stock."

    elif event_type == "ai_momentum":
        action = "BUY"
        confidence = max(impact, 4)
        resolved_assets = unique_preserve_order(resolved_assets + ["NVDA"], upper=True)
        reason = "Strong AI momentum may support semiconductor and mega-cap tech leaders."

    elif event_type == "commodity_supply_disruption":
        action = "BUY"
        confidence = max(impact, 4)
        if "ALUMINUM" in resolved_assets or "aluminum" in _combined_text(article) or "aluminium" in _combined_text(article):
            resolved_assets = unique_preserve_order(resolved_assets + ["ALUMINUM"], upper=True)
            reason = "Supply disruption may drive higher metal prices, especially aluminum."
        else:
            reason = "Commodity supply disruption may support affected raw-material prices."

    elif event_type == "safe_haven_risk_off":
        action = "BUY"
        confidence = max(impact - 1, 3)
        resolved_assets = ["GOLD"] if theme != "defense" else ["GOLD", "RTX", "LMT"]
        reason = "Risk-off conditions may support safe-haven and defense assets."

    elif event_type == "non_tradable":
        action = "HOLD"
        confidence = 1
        reason = "Event is not strong enough to justify a tradable signal."

    else:
        # theme fallback
        if theme == "tech" and sentiment == "positive" and impact >= 4:
            action = "BUY"
            confidence = impact
            reason = "Positive tech momentum may support sector leaders."
        elif theme == "tech" and sentiment == "negative" and impact >= 4:
            action = "SELL"
            confidence = impact
            reason = "Negative tech sentiment may pressure sector valuations."
        elif theme == "gold" and impact >= 4:
            action = "BUY"
            confidence = impact
            resolved_assets = unique_preserve_order(resolved_assets + ["GOLD"], upper=True)
            reason = "Risk-off conditions may support gold."
        elif theme == "oil" and impact >= 4:
            if sentiment == "positive":
                action = "BUY"
                confidence = max(impact - 1, 3)
                resolved_assets = unique_preserve_order(resolved_assets + ["OIL"], upper=True)
                reason = "Constructive oil backdrop may support energy prices."
            elif sentiment == "negative":
                action = "SELL"
                confidence = max(impact - 1, 3)
                resolved_assets = unique_preserve_order(resolved_assets + ["OIL"], upper=True)
                reason = "Negative oil backdrop may weigh on energy prices."
        elif theme == "defense" and impact >= 4:
            action = "BUY"
            confidence = impact
            resolved_assets = unique_preserve_order(resolved_assets + ["RTX", "LMT"], upper=True)
            reason = "Defense-related escalation may support military contractors."
        elif theme == "rates" and impact >= 4:
            if sentiment == "negative":
                action = "SELL"
                confidence = max(impact - 1, 3)
                resolved_assets = unique_preserve_order(resolved_assets or ["VOO", "QQQ"], upper=True)
                reason = "Rates pressure may weigh on equities."
            elif sentiment == "positive":
                action = "BUY"
                confidence = max(impact - 1, 3)
                resolved_assets = unique_preserve_order(resolved_assets or ["VOO", "QQQ"], upper=True)
                reason = "A softer rate path may support equities."

    return {
        "action": action,
        "confidence": confidence,
        "reason": reason,
        "assets": unique_preserve_order(resolved_assets, upper=True),
        "event_type": event_type,
    }



def _derive_risk_reason(action: str, confidence: int, technical_bias: str | None) -> str:
    if action == "HOLD" or confidence <= 1:
        return "Confidence too low to open position."
    if action == "BUY" and technical_bias == "bearish":
        return "Bullish signal but bearish technicals → reduced exposure."
    if action == "SELL" and technical_bias == "bullish":
        return "Bearish signal but bullish technicals → reduced exposure."
    return "Signal and technicals aligned or neutral."



def _derive_position_size(action: str, confidence: int) -> float:
    if action == "HOLD" or confidence <= 1:
        return 0.0
    if confidence >= 5:
        return 1.0
    if confidence == 4:
        return 0.7
    if confidence == 3:
        return 0.4
    if confidence == 2:
        return 0.2
    return 0.0



def generate_signal(article: Dict[str, Any] | EnrichedArticle) -> Dict[str, Any]:
    """
    Generate a trading signal from an enriched article.

    Returns:
    - action: BUY / SELL / HOLD
    - assets: list of tickers
    - confidence: 1-5
    - reason: short explanation
    """
    theme = str(_get_field(article, "theme", "") or "")
    sentiment = str(_get_field(article, "sentiment", "neutral") or "neutral")
    impact = int(_get_field(article, "impact_score", 1) or 1)
    assets = _safe_assets(article)

    event_type = _detect_event_type(article, theme, assets)
    base_signal = _build_signal_from_event(event_type, article, theme, sentiment, impact, assets)
    action = base_signal["action"]
    confidence = base_signal["confidence"]
    reason = base_signal["reason"]
    assets = base_signal["assets"]

    technicals = _get_technical_context(theme, assets)
    technical_bias = (technicals or {}).get("technical_bias")

    if technicals:
        if action == "BUY" and technical_bias == "bearish":
            confidence = max(1, confidence - 1)
            if confidence <= 2:
                action = "HOLD"
            reason = "Fundamentals are constructive, but bearish technicals reduce conviction."
        elif action == "SELL" and technical_bias == "bullish":
            confidence = max(1, confidence - 1)
            if confidence <= 2:
                action = "HOLD"
            reason = "Fundamentals are negative, but bullish technicals reduce conviction."
        else:
            confidence = _adjust_confidence(confidence, technical_bias or "neutral", action)

        reason = _merge_reason(reason, technicals)

    position_size = _derive_position_size(action, confidence)
    risk_reason = _derive_risk_reason(action, confidence, technical_bias)

    return {
        "action": action,
        "assets": assets,
        "confidence": confidence,
        "position_size": position_size,
        "reason": reason,
        "event_type": event_type,
        "technical_bias": technical_bias,
        "risk_reason": risk_reason,
        "technicals": technicals,
    }



def generate_signals(articles: List[Dict[str, Any] | EnrichedArticle]) -> List[Dict[str, Any]]:
    """
    Generate signals for a list of enriched articles.
    """
    signals = []

    for article in articles:
        signal = generate_signal(article)
        signals.append(
            {
                "title": _get_field(article, "title"),
                "signal": signal,
            }
        )

    return signals