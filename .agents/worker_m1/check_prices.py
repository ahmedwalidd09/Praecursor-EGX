import sqlite3
from pathlib import Path

db_path = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\database\praecursor.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

dates = ['2026-07-28', '2026-07-29', '2026-07-30', '2026-08-01', '2026-08-02', '2026-08-03']
for d in dates:
    cnt = conn.execute("SELECT COUNT(DISTINCT ticker) FROM source_prices WHERE trade_date = ?", (d,)).fetchone()[0]
    sample = conn.execute("SELECT ticker, open, high, low, close FROM source_prices WHERE trade_date = ? LIMIT 5", (d,)).fetchall()
    print(f"Date: {d}, Ticker count: {cnt}, Sample: {[dict(s) for s in sample]}", flush=True)

conn.close()
