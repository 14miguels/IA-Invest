from dataclasses import asdict
from datetime import datetime
import time

import yfinance as yf

from app.backtester import backtest_track_and_summarize
from app.backtester import load_tracked_performance
from app.db import init_db, insert_news, insert_signal
from app.news_enricher import enrich_articles
from app.news_fetcher import fetch_news
from app.news_filter import filter_tradable_articles
from app.risk_manager import evaluate_risk
from app.signal_engine import generate_signals
from data.open_trades_manager import (
    add_open_trade,
    load_open_trades,
    update_all_open_trades_prices,
    close_mature_open_trades,
    close_open_trade,
)


YFINANCE_PRICE_MAP = {
    "OIL": "USO",
    "GOLD": "GLD",
}

UNSUPPORTED_LIVE_PRICE_ASSETS = {
    "ALUMINUM",
    "ALUMINIUM",
}


def _candidate_trade_assets(assets: list) -> list[str]:
    candidates: list[str] = []
    seen = set()

    for asset in assets or []:
        raw_asset = str(asset or "").upper().strip()
        if not raw_asset or raw_asset in UNSUPPORTED_LIVE_PRICE_ASSETS:
            continue

        mapped = YFINANCE_PRICE_MAP.get(raw_asset, raw_asset)
        if mapped not in seen:
            seen.add(mapped)
            candidates.append(mapped)

    return candidates


def _resolve_live_price(assets: list) -> tuple[str | None, float | None]:
    for ticker in _candidate_trade_assets(assets):
        try:
            data = yf.download(ticker, period="5d", interval="1d", progress=False, auto_adjust=True)
            if data is None or data.empty:
                continue

            closes = data["Close"].dropna()
            if closes.empty:
                continue

            last_value = closes.iloc[-1]
            if hasattr(last_value, "iloc"):
                last_value = last_value.iloc[0]

            return ticker, round(float(last_value), 2)
        except Exception:
            continue

    return None, None


def _opposite_action(action: str) -> str | None:
    normalized = str(action or "").upper().strip()
    if normalized == "BUY":
        return "SELL"
    if normalized == "SELL":
        return "BUY"
    return None


def _should_open_trade(action: str, confidence: object, position_size: object) -> bool:
    normalized = str(action or "").upper().strip()
    try:
        confidence_value = int(confidence or 0)
    except (TypeError, ValueError):
        confidence_value = 0
    try:
        position_size_value = float(position_size or 0.0)
    except (TypeError, ValueError):
        position_size_value = 0.0

    return normalized in {"BUY", "SELL"} and confidence_value >= 4 and position_size_value >= 0.3


def run_pipeline() -> None:
    print("=== RUNNING FULL PIPELINE ===")
    start_total = time.time()

    # 1. Init DB
    init_db()

    # 1.5. Refresh current prices for already-open trades
    try:
        open_update_result = update_all_open_trades_prices()
        print(
            f"[OPEN TRADES UPDATE] Updated: {open_update_result.get('updated', 0)}, "
            f"Skipped: {open_update_result.get('skipped', 0)}"
        )
        if open_update_result.get("errors"):
            print(f"[OPEN TRADES UPDATE ERRORS] {len(open_update_result['errors'])} issue(s)")
    except Exception as exc:
        print(f"[OPEN TRADES UPDATE ERROR] {exc}")

    # 1.6. Close trades that exceeded holding window (time-based exit)
    try:
        close_result = close_mature_open_trades(max_days=3)
        print(f"[OPEN TRADES CLOSE] Closed: {close_result.get('closed', 0)}")
    except Exception as exc:
        print(f"[OPEN TRADES CLOSE ERROR] {exc}")

    # 2. Fetch news
    articles = fetch_news()
    print(f"Fetched {len(articles)} articles")

    articles = filter_tradable_articles(articles)
    print(f"After filtering: {len(articles)} tradable articles")

    if not articles:
        print("No tradable articles. Exiting.")
        return

    # 3. Enrich
    t0 = time.time()
    enriched_articles = enrich_articles(articles)
    print(f"Enrichment done in {time.time() - t0:.2f}s")

    if not enriched_articles:
        print("No enriched articles. Exiting.")
        return

    # 4. Store news
    inserted = 0
    duplicates = 0

    enriched_by_title = {a.title: a for a in enriched_articles}
    tracked_signals: list[dict] = []
    open_trade_candidates: list[dict] = []

    for article in enriched_articles:
        if insert_news(asdict(article)):
            inserted += 1
        else:
            duplicates += 1

    print(f"Inserted: {inserted}, Duplicates: {duplicates}")

    # 5. Generate signals (sorted by confidence)
    signals = generate_signals(enriched_articles)
    signals = sorted(signals, key=lambda x: x["signal"].get("confidence", 0), reverse=True)

    # 6. Apply risk, store signals, and then track performance
    for entry in signals:
        final_signal = evaluate_risk(entry["signal"])

        article = enriched_by_title.get(entry["title"])
        if not article:
            continue
        signal_timestamp = (
            getattr(article, "published_at", None)
            or getattr(article, "created_at", None)
            or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        insert_signal(
            {
                "title": entry["title"],
                "action": final_signal["final_action"],
                "assets": final_signal.get("assets"),
                "confidence": final_signal.get("confidence"),
                "reason": final_signal.get("reason"),
                "theme": article.theme,
                "sentiment": article.sentiment,
                "impact_score": article.impact_score,
                "position_size": final_signal.get("position_size"),
                "technical_bias": final_signal.get("technical_bias"),
                "risk_reason": final_signal.get("risk_reason"),
            }
        )
        tracked_signals.append(
            {
                "title": entry["title"],
                "action": final_signal["final_action"],
                "assets": final_signal.get("assets"),
                "confidence": final_signal.get("confidence"),
                "position_size": final_signal.get("position_size"),
                "timestamp": signal_timestamp,
                "published_at": signal_timestamp,
            }
        )
        if _should_open_trade(
            final_signal.get("final_action"),
            final_signal.get("confidence"),
            final_signal.get("position_size"),
        ):
            resolved_asset, live_price = _resolve_live_price(final_signal.get("assets") or [])
            if resolved_asset and live_price is not None:
                open_trade_candidates.append(
                    {
                        "title": entry["title"],
                        "action": final_signal["final_action"],
                        "assets": [resolved_asset],
                        "confidence": final_signal.get("confidence"),
                        "position_size": final_signal.get("position_size"),
                        "timestamp": signal_timestamp,
                        "published_at": signal_timestamp,
                        "current_price": live_price,
                        "entry_price": live_price,
                    }
                )

    # 7. Store open trades for actionable signals (deduped)
    try:
        existing_open_trades = load_open_trades(limit=5000)
        existing_open_keys = {
            (
                str(row.get("asset") or ""),
                str(row.get("action") or ""),
                str(row.get("status") or "open"),
            )
            for row in existing_open_trades
        }

        open_inserted = 0
        closed_opposites = 0
        for signal in open_trade_candidates:
            assets = signal.get("assets") or []
            first_asset = str(assets[0]) if assets else ""
            action = str(signal.get("action") or "").upper().strip()
            same_key = (first_asset, action, "open")
            opposite_key = (first_asset, _opposite_action(action) or "", "open")

            if same_key in existing_open_keys:
                continue

            opposite_trade = next(
                (
                    row for row in existing_open_trades
                    if str(row.get("asset") or "") == first_asset
                    and str(row.get("action") or "").upper().strip() == (_opposite_action(action) or "")
                    and str(row.get("status") or "open") == "open"
                ),
                None,
            )
            if opposite_trade is not None:
                close_open_trade(int(opposite_trade["id"]))
                existing_open_keys.discard(opposite_key)
                closed_opposites += 1
                continue

            add_open_trade(signal)
            existing_open_keys.add(same_key)
            open_inserted += 1

        print(f"[OPEN TRADES] Inserted: {open_inserted}, Closed Opposites: {closed_opposites}")
    except Exception as exc:
        print(f"[OPEN TRADES ERROR] {exc}")

    # 8. Track performance on the latest generated signals
    try:
        existing_rows = load_tracked_performance(limit=5000)
        existing_keys = {
            (
                str(row.get("title") or ""),
                str(row.get("asset") or ""),
                str(row.get("timestamp") or ""),
                str(row.get("action") or ""),
            )
            for row in existing_rows
        }

        candidate_signals = []
        for signal in tracked_signals:
            assets = _candidate_trade_assets(signal.get("assets") or [])
            if not assets:
                continue

            normalized_signal = dict(signal)
            normalized_signal["assets"] = assets

            first_asset = str(assets[0]) if assets else ""
            key = (
                str(signal.get("title") or ""),
                first_asset,
                str(signal.get("timestamp") or ""),
                str(signal.get("action") or ""),
            )
            if key not in existing_keys:
                candidate_signals.append(normalized_signal)

        tracking_result = backtest_track_and_summarize(candidate_signals)
        print("[PERFORMANCE TRACKING]")
        print(f"Inserted: {tracking_result.get('inserted', 0)}")
        print(f"Summary: {tracking_result.get('summary', {})}")
    except Exception as exc:
        print(f"[PERFORMANCE TRACKING ERROR] {exc}")

    print(f"=== PIPELINE FINISHED in {time.time() - start_total:.2f}s ===")


if __name__ == "__main__":
    run_pipeline()