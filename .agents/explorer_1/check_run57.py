import sqlite3

conn = sqlite3.connect('database/praecursor.db')
conn.row_factory = sqlite3.Row

top8_run57 = conn.execute("""
    SELECT symbol, rank, latest_close, next_day_label, next_day_target
    FROM scanner_signals
    WHERE run_id = 57
    ORDER BY rank ASC
    LIMIT 8
""").fetchall()

print("Top 8 signals for run 57 (2026-08-02):")
for sig in top8_run57:
    sym = sig["symbol"]
    bars = conn.execute("""
        SELECT trade_date, high, close
        FROM source_prices
        WHERE ticker = ? AND trade_date > '2026-08-02'
        ORDER BY trade_date ASC
    """, (sym,)).fetchall()
    print(f"Rank {sig['rank']}: {sym} | close={sig['latest_close']} | target={sig['next_day_target']} | bars after 08-02: {[dict(b) for b in bars]}")

conn.close()
