import sqlite3
from pathlib import Path

root = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX")
db_path = root / "database" / "praecursor.db"
conn = sqlite3.connect(db_path)

print("Unique run_ids in scanner_signals:", [r[0] for r in conn.execute("SELECT DISTINCT run_id FROM scanner_signals").fetchall()])
print("Unique run_ids in scanner_signal_outcomes:", [r[0] for r in conn.execute("SELECT DISTINCT run_id FROM scanner_signal_outcomes").fetchall()])
print("Unique run_ids in scanner_runs:", [r[0] for r in conn.execute("SELECT id FROM scanner_runs").fetchall()])
