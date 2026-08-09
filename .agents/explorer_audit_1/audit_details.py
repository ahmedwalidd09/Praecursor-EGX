import sqlite3
import os
import sys

print("Opening SQLite...", flush=True)
conn = sqlite3.connect("database/praecursor.db", timeout=10.0)
conn.row_factory = sqlite3.Row

print("=== SCANNER RUNS GROUPED BY DATE ===", flush=True)
runs_summary = conn.execute("""
    SELECT date(generated_at) as run_date, MIN(id) as min_id, MAX(id) as max_id, COUNT(*) as run_count
    FROM scanner_runs
    GROUP BY date(generated_at)
    ORDER BY run_date ASC
""").fetchall()
for r in runs_summary:
    print(dict(r), flush=True)

print("\n=== SOURCE PRICES TRADE DATES ===", flush=True)
trade_dates = conn.execute("""
    SELECT trade_date, COUNT(DISTINCT ticker) as ticker_count, COUNT(*) as total_rows
    FROM source_prices
    GROUP BY trade_date
    ORDER BY trade_date ASC
""").fetchall()
for td in trade_dates:
    print(dict(td), flush=True)

print("\n=== CHECKING NEXT BAR LOOKUP FOR EACH RUN DATE ===", flush=True)
for r in runs_summary:
    run_date = r["run_date"]
    max_id = r["max_id"]
    top8 = conn.execute("""
        SELECT rank, symbol, latest_close, next_day_target
        FROM scanner_signals
        WHERE run_id = ?
        ORDER BY rank ASC
        LIMIT 8
    """, (max_id,)).fetchall()
    
    found_count = 0
    for sig in top8:
        sym = sig["symbol"]
        next_bar = conn.execute("""
            SELECT trade_date, MAX(high) as high, MIN(low) as low, close
            FROM source_prices
            WHERE ticker = ? AND trade_date > ?
            GROUP BY trade_date
            ORDER BY trade_date ASC
            LIMIT 1
        """, (sym, run_date)).fetchone()
        if next_bar and next_bar["high"] is not None:
            found_count += 1
    print(f"Run Date: {run_date} (Run ID {max_id}): {found_count}/8 candidates had next_bar in source_prices.", flush=True)

conn.close()
