import sys
import sqlite3
from pathlib import Path

root = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX")
sys.path.insert(0, str(root / "src"))

from praecursor.analysis.accuracy_tracker import AccuracyTracker

db_path = root / "database" / "praecursor.db"
print("DB Path:", db_path)

conn = sqlite3.connect(db_path)
cur = conn.cursor()
print("scanner_runs count:", cur.execute("SELECT count(*) FROM scanner_runs").fetchone()[0])
print("scanner_signals count:", cur.execute("SELECT count(*) FROM scanner_signals").fetchone()[0])
print("scanner_signal_outcomes count:", cur.execute("SELECT count(*) FROM scanner_signal_outcomes").fetchone()[0])
conn.close()

tracker = AccuracyTracker()
print("Updating historical outcomes...")
tracker.update_historical_outcomes()

csv_path = root / "reports" / "archive" / "accuracy_history_archive.csv"
print("CSV Exists:", csv_path.exists())

if csv_path.exists():
    lines = [line for line in csv_path.read_text(encoding="utf-8").strip().split("\n") if line.strip()]
    print(f"CSV Non-empty Lines count: {len(lines)}")
    print(f"CSV Evaluation Records count (excluding header): {len(lines) - 1}")
    if len(lines) > 1:
        print("Header:", lines[0])
        print("First Record:", lines[1])
        print("Last Record:", lines[-1])

stats = tracker.get_accuracy_stats()
print("Stats:", stats["next_day"])
