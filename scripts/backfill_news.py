

from dataclasses import asdict

from app.db import init_db, insert_news
from app.news_enricher import enrich_articles
from app.news_fetcher import fetch_news



def main() -> None:
    print("Initializing database...")
    init_db()

    print("Fetching news for backfill...")
    articles = fetch_news()
    print(f"Fetched {len(articles)} articles")

    print("Enriching fetched articles...")
    enriched_articles = enrich_articles(articles)

    inserted = 0
    duplicates = 0

    for article in enriched_articles:
        success = insert_news(asdict(article))
        if success:
            inserted += 1
        else:
            duplicates += 1

    print("\nBackfill complete.")
    print(f"Inserted: {inserted}")
    print(f"Skipped duplicates: {duplicates}")


if __name__ == "__main__":
    main()