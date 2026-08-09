import sqlite3
from pathlib import Path

db_path = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\database\praecursor.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

print("=== TABLES ===", flush=True)
tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print(tables, flush=True)

print("\n=== SCANNER RUNS ===", flush=True)
runs = conn.execute("SELECT id, generated_at, date(generated_at) as run_date FROM scanner_runs ORDER BY id ASC").fetchall()
print(f"Total scanner runs: {len(runs)}", flush=True)
for r in runs:
    print(dict(r), flush=True)

print("\n=== SCANNER SIGNALS COUNT PER RUN ===", flush=True)
sig_counts = conn.execute("SELECT run_id, COUNT(*) as cnt FROM scanner_signals GROUP BY run_id").fetchall()
for sc in sig_counts:
    print(dict(sc), flush=True)

print("\n=== SCANNER OUTCOMES ===", flush=True)
outcomes = conn.execute("SELECT run_id, signal_date, count(*) as cnt FROM scanner_signal_outcomes GROUP BY signal_date").fetchall()
for o in outcomes:
    print(dict(o), flush=True)

print("\n=== SOURCE PRICES DATE RANGE ===", flush=True)
dates = conn.execute("SELECT MIN(trade_date), MAX(trade_date), COUNT(DISTINCT trade_date), COUNT(DISTINCT ticker) FROM source_prices").fetchone()
print(dict(dates), flush=True)

print("\n=== SOURCE PRICES LAST 10 DATES ===", flush=True)
last_dates = conn.execute("SELECT DISTINCT trade_date FROM source_prices ORDER BY trade_date DESC LIMIT 10").fetchall()
print([r[0] for r in last_dates], flush=True)

conn.close()
