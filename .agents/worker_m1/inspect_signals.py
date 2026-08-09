import sqlite3
from pathlib import Path

db_path = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\database\praecursor.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

print("=== TOP 8 SIGNALS FOR RUN 25 (2026-08-01) ===", flush=True)
top8_25 = conn.execute("SELECT rank, symbol, latest_close, next_day_label, next_day_target FROM scanner_signals WHERE run_id = 25 ORDER BY rank ASC LIMIT 8").fetchall()
for r in top8_25:
    print(dict(r), flush=True)

print("\n=== TOP 8 SIGNALS FOR RUN 57 (2026-08-02) ===", flush=True)
top8_57 = conn.execute("SELECT rank, symbol, latest_close, next_day_label, next_day_target FROM scanner_signals WHERE run_id = 57 ORDER BY rank ASC LIMIT 8").fetchall()
for r in top8_57:
    print(dict(r), flush=True)

print("\n=== TOP 8 SIGNALS FOR RUN 62 (2026-08-03) ===", flush=True)
top8_62 = conn.execute("SELECT rank, symbol, latest_close, next_day_label, next_day_target FROM scanner_signals WHERE run_id = 62 ORDER BY rank ASC LIMIT 8").fetchall()
for r in top8_62:
    print(dict(r), flush=True)

print("\n=== EXISTING OUTCOMES IN DB ===", flush=True)
outcomes = conn.execute("SELECT * FROM scanner_signal_outcomes").fetchall()
for o in outcomes:
    print(dict(o), flush=True)

conn.close()
