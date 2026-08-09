import sqlite3

conn = sqlite3.connect(r'C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\database\praecursor.db')
cursor = conn.cursor()

# Check scanner_runs
cursor.execute('SELECT id, generated_at, source_name, success_count, error_count FROM scanner_runs ORDER BY id DESC LIMIT 5')
print("=== scanner_runs ===")
for row in cursor.fetchall():
    print(row)

# Check scanner_signals
cursor.execute('SELECT run_id, symbol, rank, opportunity_score, predictor_label, latest_close FROM scanner_signals ORDER BY run_id DESC, rank ASC LIMIT 20')
print("\n=== scanner_signals (latest run) ===")
for row in cursor.fetchall():
    print(row)

# Check scanner_signal_outcomes
cursor.execute('SELECT run_id, symbol, signal_date, next_day_label, next_day_hit, next_day_return FROM scanner_signal_outcomes ORDER BY id DESC LIMIT 20')
print("\n=== scanner_signal_outcomes ===")
for row in cursor.fetchall():
    print(row)

# Check source_prices count
cursor.execute('SELECT COUNT(*) FROM source_prices')
print(f"\n=== source_prices count: {cursor.fetchone()[0]} ===")

# Check distinct tickers in source_prices
cursor.execute('SELECT COUNT(DISTINCT ticker) FROM source_prices')
print(f"=== distinct tickers in source_prices: {cursor.fetchone()[0]} ===")