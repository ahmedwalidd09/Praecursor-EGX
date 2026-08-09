import sqlite3
from pathlib import Path
import csv

root = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX")

db_paths = [
    root / "database" / "praecursor.db",
    root / "config" / "praecursor.db",
    root / "data" / "signal_history.db",
    root / "reports" / "signal_history.db",
    root / "signal_history.db",
]

for db in db_paths:
    print(f"=== DB: {db} (exists: {db.exists()}) ===")
    if db.exists():
        conn = sqlite3.connect(db)
        tables = [t[0] for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        print("  Tables:", tables)
        for t in tables:
            count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"    Table {t}: {count} rows")

csv_path = root / "reports" / "archive" / "accuracy_history_archive.csv"
print(f"=== CSV: {csv_path} (exists: {csv_path.exists()}) ===")
if csv_path.exists():
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)
        print(f"  Total lines (including header): {len(rows)}")
        if len(rows) > 0:
            print("  Header:", rows[0])
        if len(rows) > 1:
            print("  First row:", rows[1])
            print("  Last row:", rows[-1])
