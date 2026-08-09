import sqlite3

conn = sqlite3.connect("database/praecursor.db")
conn.row_factory = sqlite3.Row

print("=== RECENT TRADE DATES IN SOURCE_PRICES ===")
dates = conn.execute("""
    SELECT trade_date, COUNT(DISTINCT ticker) as cnt
    FROM source_prices
    WHERE trade_date >= '2026-07-20'
    GROUP BY trade_date
    ORDER BY trade_date ASC
""").fetchall()
for d in dates:
    print(dict(d))

print("\n=== SCANNER RUNS IN DATABASE ===")
runs = conn.execute("""
    SELECT id, generated_at, date(generated_at) as run_date, success_count
    FROM scanner_runs
    ORDER BY id ASC
""").fetchall()
for r in runs:
    print(dict(r))

conn.close()
