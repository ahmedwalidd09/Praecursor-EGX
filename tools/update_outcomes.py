import sys
import sqlite3
from pathlib import Path

# Add src to path
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))

from praecursor.analysis.accuracy_tracker import AccuracyTracker

if __name__ == "__main__":
    db_path = root / "database" / "praecursor.db"
    tracker = AccuracyTracker(database_path=db_path)
    tracker.update_historical_outcomes()
    print("Updated historical outcomes.")
