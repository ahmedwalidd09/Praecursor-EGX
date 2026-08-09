import sqlite3
import csv
from pathlib import Path

db_path = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\database\praecursor.db")
csv_path = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\reports\archive\accuracy_history_archive.csv")

print("=== DB CHECK ===")
if db_path.exists():
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print("Tables:", tables)

    for t in tables:
        cnt = c.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        print(f"Table {t}: {cnt} rows")

    if "scanner_signal_outcomes" in tables:
        rows = c.execute("SELECT * FROM scanner_signal_outcomes").fetchall()
        print(f"\nscanner_signal_outcomes ({len(rows)} rows):")
        for r in rows[:10]:
            print(dict(r))

    if "scanner_runs" in tables:
        runs = c.execute("SELECT * FROM scanner_runs").fetchall()
        print(f"\nscanner_runs ({len(runs)} rows):")
        for r in runs[:10]:
            print(dict(r))

    conn.close()

print("\n=== CSV CHECK ===")
if csv_path.exists():
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        print(f"CSV total rows: {len(reader)}")
        for r in reader[:10]:
            print(r)
