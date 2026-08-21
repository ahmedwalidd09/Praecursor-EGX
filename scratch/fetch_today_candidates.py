import sqlite3
import pandas as pd

conn = sqlite3.connect('database/praecursor.db')
query = """
SELECT symbol, next_day_prob, next_day_target, next_day_stop, kelly_fraction 
FROM scanner_results 
WHERE scan_date='2026-08-10' AND next_day_label='Candidate' 
ORDER BY next_day_prob DESC LIMIT 8;
"""
df = pd.read_sql_query(query, conn)
print(df.to_markdown(index=False))
