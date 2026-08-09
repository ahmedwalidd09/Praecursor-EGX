import sqlite3
from pathlib import Path

root = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX")
db_path = root / "database" / "praecursor.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

print("Checking scanner_signals for run_id = 25:")
signals = conn.execute("SELECT symbol, rank, latest_close, next_day_target FROM scanner_signals WHERE run_id = 25 LIMIT 5").fetchall()
for s in signals:
    print(dict(s))

print("Checking day_runs:")
day_runs = conn.execute("""
    SELECT MAX(id) as run_id, date(generated_at) as run_date
    FROM scanner_runs
    GROUP BY date(generated_at)
""").fetchall()
for d in day_runs:
    print(dict(d))

print("Testing JOIN between scanner_signals and day_runs:")
top8 = conn.execute("""
    WITH day_runs AS (
        SELECT MAX(id) as run_id, date(generated_at) as run_date
        FROM scanner_runs
        GROUP BY date(generated_at)
    )
    SELECT dr.run_date as signal_date, s.run_id, s.symbol, s.next_day_target, s.latest_close,
           s.rank
    FROM scanner_signals s
    JOIN day_runs dr ON s.run_id = dr.run_id
    WHERE dr.run_id = 25
    LIMIT 5
""").fetchall()
print(f"Result count for run 25: {len(top8)}")
for t in top8:
    print(dict(t))
