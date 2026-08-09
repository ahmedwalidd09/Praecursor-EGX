import sqlite3
from pathlib import Path

db_path = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\database\praecursor.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("--- scanner_runs ---")
runs = cur.execute("SELECT id, generated_at, date(generated_at) as run_date FROM scanner_runs ORDER BY id").fetchall()
for r in runs:
    print(dict(r))

print("\n--- scanner_signal_outcomes count ---")
print("Total rows:", cur.execute("SELECT COUNT(*) FROM scanner_signal_outcomes").fetchone()[0])
print("Rows with next_day_hit IS NOT NULL:", cur.execute("SELECT COUNT(*) FROM scanner_signal_outcomes WHERE next_day_hit IS NOT NULL").fetchone()[0])

outcomes = cur.execute("SELECT * FROM scanner_signal_outcomes ORDER BY signal_date, run_id, symbol").fetchall()
print(f"\nPrinting all {len(outcomes)} outcome rows:")
for o in outcomes:
    print(dict(o))

conn.close()
