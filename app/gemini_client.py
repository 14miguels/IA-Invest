import json
import os
from typing import Any, Dict

from dotenv import load_dotenv
from google import genai
from google.genai import types

from app.config import LLM_MODEL

load_dotenv()

DEFAULT_MODEL = LLM_MODEL


class GeminiClientError(Exception):
    """Raised when the Gemini classification request fails."""



def get_api_key() -> str:
    """Return the Gemini API key from environment variables."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise GeminiClientError("GEMINI_API_KEY is not set.")
    return api_key



def build_prompt(article: Dict[str, Any]) -> str:
    """Build a concise prompt for financial news classification."""
    title = str(article.get("title") or "")
    summary = str(article.get("summary") or "")
    source = str(article.get("source") or "")

    return f"""
Classify this financial news article.

Return only valid JSON with exactly these fields:
- sentiment: one of [positive, negative, neutral]
- theme: one of [tech, defense, gold, oil, rates, macro]
- assets: array of strings with relevant tickers/assets like NVDA, QQQ, RTX, LMT, GOLD, OIL, VOO
- impact_score: integer from 1 to 5
- short_reason: short explanation under 25 words

Title: {title}
Summary: {summary}
Source: {source}
""".strip()



def classify_with_gemini(
    article: Dict[str, Any],
    model: str = DEFAULT_MODEL,
) -> Dict[str, Any]:
    """Classify a news article using the Gemini API."""
    client = genai.Client(api_key=get_api_key())
    prompt = build_prompt(article)

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0,
            ),
        )
    except Exception as exc:
        raise GeminiClientError(f"Gemini request failed: {exc}") from exc

    output_text = (getattr(response, "text", "") or "").strip()
    if not output_text:
        raise GeminiClientError("Gemini returned an empty response.")

    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise GeminiClientError(
            f"Gemini response was not valid JSON: {output_text}"
        ) from exc

    required_keys = {"sentiment", "theme", "assets", "impact_score", "short_reason"}
    missing = required_keys - parsed.keys()
    if missing:
        raise GeminiClientError(f"Missing keys in Gemini response: {sorted(missing)}")

    return {
        "sentiment": str(parsed["sentiment"]),
        "theme": str(parsed["theme"]),
        "assets": [str(asset) for asset in parsed.get("assets", [])],
        "impact_score": int(parsed["impact_score"]),
        "short_reason": str(parsed["short_reason"]),
    }