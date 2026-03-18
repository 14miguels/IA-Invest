

"""
Centralized prompts for LLM interactions.
"""


def build_classification_prompt(article: dict) -> str:
    """
    Build the prompt for classifying a news article.
    """
    title = article.get("title", "")
    summary = article.get("summary", "")

    return f"""
You are a financial news classifier.

Classify the following article into a structured JSON output.

Rules:
- sentiment: one of [positive, negative, neutral]
- impact_score: integer from 1 (low) to 5 (high)
- theme: one of [tech, defense, oil, gold, rates, macro, other]
- assets: list of relevant tickers (e.g., NVDA, TSLA, QQQ, RTX, LMT, GLD, USO)
- short_reason: short explanation (max 20 words)

Return ONLY valid JSON.

Article:
Title: {title}
Summary: {summary}

Output format:
{{
  "sentiment": "positive|negative|neutral",
  "impact_score": 1-5,
  "theme": "tech|defense|oil|gold|rates|macro|other",
  "assets": ["TICKER"],
  "short_reason": "..."
}}
"""


def build_signal_prompt(article: dict, technicals: dict | None = None) -> str:
    """
    (Optional future use) Prompt for generating signals via LLM.
    Currently not used but kept for extensibility.
    """
    base = f"""
You are a trading decision assistant.

Article:
Title: {article.get('title')}
Summary: {article.get('summary')}

Provide:
- action: BUY / SELL / HOLD
- assets: list of tickers
- confidence: 1-5
- reason: short explanation
"""

    if technicals:
        base += f"""

Technicals:
RSI: {technicals.get('rsi')}
MACD: {technicals.get('macd')}
Signal: {technicals.get('macd_signal')}
Bias: {technicals.get('technical_bias')}
"""

    return base