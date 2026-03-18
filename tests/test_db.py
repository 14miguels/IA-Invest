

import os
import tempfile

from app.db import init_db, insert_news, insert_signal, get_latest_news


def test_db_flow():
    """Basic integration test for DB operations."""

    # Create temp DB path
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")

        # Monkey patch DB_PATH
        import app.config as config
        config.DB_PATH = db_path

        # Init DB
        init_db()

        # Insert news
        article = {
            "title": "Test Article",
            "summary": "This is a test summary long enough to pass validation.",
            "source": "Test",
            "sentiment": "positive",
            "impact_score": 4,
            "theme": "tech",
            "assets": ["NVDA"],
        }

        assert insert_news(article) is True

        # Duplicate insert should fail
        assert insert_news(article) is False

        # Fetch news
        news = get_latest_news()
        assert len(news) == 1
        assert news[0]["title"] == "Test Article"

        # Insert signal
        signal = {
            "title": "Test Article",
            "action": "BUY",
            "assets": ["NVDA"],
            "confidence": 4,
            "reason": "Test reason",
            "theme": "tech",
            "sentiment": "positive",
            "impact_score": 4,
        }

        insert_signal(signal)

        print("DB test passed ✔")


if __name__ == "__main__":
    test_db_flow()