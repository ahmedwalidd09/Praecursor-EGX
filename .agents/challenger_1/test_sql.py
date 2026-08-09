import sqlite3
from pathlib import Path

db_path = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\database\praecursor.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

query = """
WITH day_runs AS (
    SELECT MAX(id) as run_id, date(generated_at) as run_date
    FROM scanner_runs
    GROUP BY date(generated_at)
),
top8 AS (
    SELECT dr.run_date as signal_date, s.run_id, s.symbol, s.next_day_target, s.latest_close,
           ROW_NUMBER() OVER(PARTITION BY s.run_id ORDER BY s.rank ASC) as rn
    FROM scanner_signals s
    JOIN day_runs dr ON s.run_id = dr.run_id
)
SELECT o.signal_date, o.run_id, o.symbol,
       COALESCE(t.latest_close, s.latest_close, 0.0) as latest_close,
       COALESCE(t.next_day_target, s.next_day_target, 0.0) as next_day_target,
       o.next_day_label, o.next_day_hit, o.next_day_return,
       COALESCE(o.next_day_max_return, 0.0) as next_day_max_return
FROM scanner_signal_outcomes o
LEFT JOIN top8 t ON (t.run_id = o.run_id OR t.signal_date = o.signal_date) AND t.symbol = o.symbol
LEFT JOIN scanner_signals s ON s.run_id = o.run_id AND s.symbol = o.symbol
WHERE o.next_day_hit IS NOT NULL
ORDER BY o.signal_date ASC, o.run_id ASC, o.id ASC
"""

rows = cur.execute(query).fetchall()
print("Query returned rows count:", len(rows))
for r in rows[:10]:
    print(dict(r))

conn.close()
