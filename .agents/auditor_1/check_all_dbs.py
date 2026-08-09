import sqlite3
import csv
from pathlib import Path

root = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX")
db_files = list(root.rglob("*.db"))

print(f"Found {len(db_files)} .db files:")

for db_file in db_files:
    if ".agents" in db_file.parts:
        continue
    print(f"\n==========================================")
    print(f"DB FILE: {db_file}")
    print(f"Size: {db_file.stat().st_size} bytes")
    try:
        conn = sqlite3.connect(str(db_file), timeout=2.0)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        print(f"Tables: {tables}")
        for t in tables:
            cnt = c.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            print(f"  Table '{t}': {cnt} rows")
            if t == "scanner_signal_outcomes":
                rows = c.execute("SELECT * FROM scanner_signal_outcomes").fetchall()
                print(f"  scanner_signal_outcomes rows count: {len(rows)}")
                for r in rows[:5]:
                    print("   ", dict(r))
            elif t == "scanner_runs":
                runs = c.execute("SELECT * FROM scanner_runs").fetchall()
                print(f"  scanner_runs count: {len(runs)}")
                for r in runs[:5]:
                    print("   ", dict(r))
        conn.close()
    except Exception as e:
        print(f"Error reading {db_file}: {e}")

print("\n==========================================")
csv_file = root / "reports" / "archive" / "accuracy_history_archive.csv"
print(f"CSV Archive: {csv_file}")
if csv_file.exists():
    with open(csv_file, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        print(f"CSV Total Rows: {len(rows)}")
        for r in rows[:10]:
            print(r)
