import sqlite3
import csv
from pathlib import Path

project_root = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX")
db_path = project_root / "database" / "praecursor.db"
archive_path = project_root / "reports" / "archive" / "accuracy_history_archive.csv"

print("Checking Database:", db_path)
if not db_path.exists():
    print("Database file NOT FOUND!")
else:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print("Tables in database:", tables)

    for t in ["scanner_runs", "scanner_signals", "scanner_signal_outcomes", "source_prices"]:
        if t in tables:
            cnt = cursor.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"Table {t}: {cnt} rows")
        else:
            print(f"Table {t}: NOT FOUND")

    if "scanner_signal_outcomes" in tables:
        print("\n--- scanner_signal_outcomes samples (first 10) ---")
        rows = cursor.execute("SELECT * FROM scanner_signal_outcomes LIMIT 10").fetchall()
        for r in rows:
            print(dict(r))

    if "scanner_runs" in tables:
        print("\n--- scanner_runs ---")
        rows = cursor.execute("SELECT * FROM scanner_runs").fetchall()
        for r in rows:
            print(dict(r))

    conn.close()

print("\nChecking CSV Archive:", archive_path)
if not archive_path.exists():
    print("Archive CSV NOT FOUND!")
else:
    with open(archive_path, mode="r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        print(f"CSV Total Rows: {len(reader)}")
        if len(reader) > 0:
            print("First row:", reader[0])
            print("Last row:", reader[-1])
