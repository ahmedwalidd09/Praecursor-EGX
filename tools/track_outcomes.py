"""
Outcome Tracker for Praecursor-EGX

Evaluates previous scanner predictions against actual market data
to determine if the targets were hit. This forms the critical feedback
loop for the ML models.
"""

import argparse
import logging
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from praecursor.analysis.accuracy_tracker import AccuracyTracker, track_outcomes_from_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = ROOT / "database" / "praecursor.db"
DEFAULT_CSV_PATH = ROOT / "reports" / "accuracy_history_archive.csv"


def track_outcomes(db_path: Path | str | None = None, csv_path: Path | str | None = None) -> int:
    resolved_db = Path(db_path) if db_path else DB_PATH
    resolved_csv = Path(csv_path) if csv_path else DEFAULT_CSV_PATH

    logger.info(f"Running Outcome Tracker on {resolved_db}...")
    backfilled = track_outcomes_from_db(resolved_db)

    if resolved_db.exists():
        try:
            tracker = AccuracyTracker(db_path=resolved_db)
            archive_file = tracker.export_accuracy_history_archive(resolved_csv)
            logger.info(f"Exported accuracy history archive to {archive_file}")
            summary = tracker.get_summary()
            logger.info(
                f"Accuracy Summary: total={summary.get('total_signals')}, "
                f"hits={summary.get('hits')}, win_rate={summary.get('win_rate')}%, "
                f"avg_return={summary.get('avg_return')}%"
            )
        except Exception as exc:
            logger.warning(f"Could not export accuracy history archive: {exc}")

    return backfilled


def main() -> int:
    parser = argparse.ArgumentParser(description="Track signal outcomes and export historical accuracy archive.")
    parser.add_argument("--db", type=str, default=str(DB_PATH), help="Path to sqlite database")
    parser.add_argument("--csv", type=str, default=str(DEFAULT_CSV_PATH), help="Path to output CSV archive")
    args = parser.parse_args()

    track_outcomes(db_path=args.db, csv_path=args.csv)
    return 0


if __name__ == "__main__":
    sys.exit(main())

