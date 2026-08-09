import sqlite3
import csv
from pathlib import Path
from praecursor.analysis.accuracy_tracker import AccuracyTracker

root = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX")
db_path = root / "database" / "praecursor.db"

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
print("--- scanner_runs ---", conn.execute("SELECT COUNT(*) FROM scanner_runs").fetchone()[0])
print("--- scanner_signals ---", conn.execute("SELECT COUNT(*) FROM scanner_signals").fetchone()[0])
print("--- scanner_signal_outcomes ---", conn.execute("SELECT COUNT(*) FROM scanner_signal_outcomes").fetchone()[0])
print("--- source_prices ---", conn.execute("SELECT COUNT(*) FROM source_prices").fetchone()[0])

tracker = AccuracyTracker(db_path)
tracker.update_historical_outcomes()

csv_path = root / "reports" / "archive" / "accuracy_history_archive.csv"
print(f"--- Archive CSV exists: {csv_path.exists()} ---")
with open(csv_path, encoding="utf-8") as f:
    rows = list(csv.reader(f))
    print("CSV line count:", len(rows))
    if len(rows) > 1:
        print("First 3 data rows:")
        for r in rows[1:4]:
            print(r)
        print("Last 3 data rows:")
        for r in rows[-3:]:
            print(r)
