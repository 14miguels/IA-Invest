from dataclasses import asdict

from app.db import init_db, insert_news, insert_signal
from app.news_fetcher import fetch_news
from app.news_enricher import enrich_articles
from app.signal_engine import generate_signals
from app.risk_manager import evaluate_risk
from app.backtester import backtest_track_and_summarize
from app.backtester import load_tracked_performance
import time
from app.news_filter import filter_tradable_articles


def run_pipeline() -> None:
    print("=== RUNNING FULL PIPELINE ===")
    start_total = time.time()

    # 1. Init DB
    init_db()

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
                "timestamp": getattr(article, "published_at", None) or getattr(article, "created_at", None),
                "published_at": getattr(article, "published_at", None) or getattr(article, "created_at", None),
            }
        )

    # 7. Track performance on the latest generated signals
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
            assets = signal.get("assets") or []
            first_asset = str(assets[0]) if assets else ""
            key = (
                str(signal.get("title") or ""),
                first_asset,
                str(signal.get("timestamp") or ""),
                str(signal.get("action") or ""),
            )
            if key not in existing_keys:
                candidate_signals.append(signal)

        tracking_result = backtest_track_and_summarize(candidate_signals)
        print("[PERFORMANCE TRACKING]")
        print(f"Inserted: {tracking_result.get('inserted', 0)}")
        print(f"Summary: {tracking_result.get('summary', {})}")
    except Exception as exc:
        print(f"[PERFORMANCE TRACKING ERROR] {exc}")

    print(f"=== PIPELINE FINISHED in {time.time() - start_total:.2f}s ===")


if __name__ == "__main__":
    run_pipeline()