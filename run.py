import argparse
import time

from app.main import main as run_debug_pipeline
from scripts.backfill_news import main as backfill_news
from scripts.run_pipeline import run_pipeline

from data.open_trades_manager import init_open_trades


MODE_RUN = "run"
MODE_BACKFILL = "backfill"
MODE_DEBUG = "debug"


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for the project entrypoint."""
    parser = argparse.ArgumentParser(
        description="Run the Invest news, signal, and backfill pipeline."
    )
    parser.add_argument(
        "--mode",
        choices=[MODE_RUN, MODE_BACKFILL, MODE_DEBUG],
        default=MODE_RUN,
        help="run = full pipeline, backfill = insert enriched news only, debug = verbose pipeline output",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run continuously in a loop.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=600,
        help="Sleep interval in seconds between runs when --loop is set (default: 600).",
    )
    return parser


def main() -> None:
    """Main root entrypoint for the Invest project."""
    parser = build_parser()
    args = parser.parse_args()

    # Ensure open trades table exists
    init_open_trades()

    def _run_once():
        if args.mode == MODE_RUN:
            run_pipeline()
        elif args.mode == MODE_BACKFILL:
            backfill_news()
        elif args.mode == MODE_DEBUG:
            run_debug_pipeline()
        else:
            raise ValueError(f"Unsupported mode: {args.mode}")

    if args.loop:
        while True:
            print("=== RUNNING PIPELINE ===")
            _run_once()
            print(f"Sleeping {args.interval} seconds...")
            time.sleep(args.interval)
    else:
        _run_once()


if __name__ == "__main__":
    main()