import sqlite3
import json

conn = sqlite3.connect(r'C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\database\praecursor.db')
conn.row_factory = sqlite3.Row

tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables:", tables)

runs = [dict(r) for r in conn.execute("SELECT * FROM scanner_runs").fetchall()]
print("Scanner Runs:")
print(json.dumps(runs, indent=2))

latest_run_id = runs[-1]['id'] if runs else None
if latest_run_id:
    signals = [dict(r) for r in conn.execute("SELECT symbol, rank, latest_close, next_day_target, next_day_score FROM scanner_signals WHERE run_id = ? ORDER BY rank ASC", (latest_run_id,)).fetchall()]
    print(f"Signals for run_id {latest_run_id}:")
    print(json.dumps(signals, indent=2))
