import sqlite3
from pathlib import Path

db_path = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\database\praecursor.db")
conn = sqlite3.connect(db_path)
cols = conn.execute("PRAGMA table_info(source_prices)").fetchall()
print("source_prices columns:", cols, flush=True)
sample = conn.execute("SELECT * FROM source_prices LIMIT 1").fetchone()
print("Sample row:", sample, flush=True)
conn.close()
