import sqlite3

conn = sqlite3.connect('database/praecursor.db')
cursor = conn.cursor()
dates = cursor.execute("SELECT MIN(trade_date), MAX(trade_date), COUNT(DISTINCT trade_date) FROM source_prices").fetchone()
print(f"source_prices dates: min={dates[0]}, max={dates[1]}, distinct_dates={dates[2]}")

distinct_dates = cursor.execute("SELECT DISTINCT trade_date FROM source_prices ORDER BY trade_date DESC LIMIT 10").fetchall()
print("Recent trade dates in source_prices:", [d[0] for d in distinct_dates])
conn.close()
