from dataclasses import asdict

import time

from app.db import init_db, insert_news, insert_signal
from app.news_fetcher import fetch_news
from app.news_enricher import enrich_articles
from app.risk_manager import evaluate_risk
from app.signal_engine import generate_signals
from app.news_filter import filter_tradable_articles



def main() -> None:
    print("Initializing database...")
    init_db()
    start_total = time.time()

    print("Fetching news...")
    articles = fetch_news()
    print(f"Fetched {len(articles)} articles")

    # 🔥 FILTER NON-TRADABLE NEWS
    articles = filter_tradable_articles(articles)
    print(f"After filtering: {len(articles)} tradable articles")

    if not articles:
        print("No articles fetched. Exiting.")
        return

    print("Enriching articles...")
    t0 = time.time()
    enriched_articles = enrich_articles(articles)
    print(f"Enrichment done in {time.time() - t0:.2f}s")

    if not enriched_articles:
        print("No enriched articles. Exiting.")
        return

    inserted = 0
    duplicates = 0

    enriched_by_title = {article.title: article for article in enriched_articles}

    for article in enriched_articles:
        success = insert_news(asdict(article))
        if success:
            inserted += 1
        else:
            duplicates += 1

    print(f"Inserted {inserted} new articles")
    print(f"Skipped {duplicates} duplicates")

    print("\nGenerating signals...")
    signals = generate_signals(enriched_articles)
    signals = sorted(signals, key=lambda x: x["signal"].get("confidence", 0), reverse=True)

    risk_adjusted_signals = []

    for signal_entry in signals:
        raw_signal = signal_entry["signal"]
        final_signal = evaluate_risk(raw_signal)
        risk_adjusted_signals.append(
            {
                "title": signal_entry["title"],
                "signal": final_signal,
            }
        )

        matching_article = enriched_by_title.get(signal_entry["title"])
        if matching_article is None:
            continue

        signal_data = {
            "title": signal_entry["title"],
            "action": final_signal["final_action"],
            "assets": final_signal["assets"],
            "confidence": final_signal["confidence"],
            "position_size": final_signal.get("position_size"),
            "reason": final_signal["reason"],
            "theme": matching_article.theme,
            "sentiment": matching_article.sentiment,
            "impact_score": matching_article.impact_score,
            "technical_bias": (final_signal.get("technicals") or {}).get("technical_bias"),
            "risk_reason": final_signal.get("risk_reason"),
            "technicals": final_signal.get("technicals"),
        }
        insert_signal(signal_data)

    for signal_entry in risk_adjusted_signals[:10]:
        signal = signal_entry["signal"]
        print("\n---")
        print(f"Title: {signal_entry['title']}")
        print(f"Action: {signal['final_action']}")
        assets_str = ', '.join(signal.get('assets') or [])
        print(f"Assets: {assets_str}")
        print(f"Confidence: {signal['confidence']}")
        print(f"Position Size: {signal['position_size']}")
        print(f"Reason: {signal['reason']}")
        print(f"Risk: {signal['risk_reason']}")

    print(f"\nTotal runtime: {time.time() - start_total:.2f}s")


if __name__ == "__main__":
    main()