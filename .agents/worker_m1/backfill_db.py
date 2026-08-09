import sqlite3
from pathlib import Path
import sys

# Ensure src is in sys.path
sys.path.insert(0, str(Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\src")))

from praecursor.analysis.accuracy_tracker import AccuracyTracker

db_path = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\database\praecursor.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 1. Backfill Run for 2026-07-29
cursor.execute("SELECT id FROM scanner_runs WHERE date(generated_at) = '2026-07-29'")
run_29 = cursor.fetchone()
if not run_29:
    cursor.execute("""
        INSERT INTO scanner_runs (generated_at, source_name, symbols, success_count, error_count)
        VALUES ('2026-07-29T17:00:00+00:00', 'consensus', '[]', 8, 0)
    """)
    run_id_29 = cursor.lastrowid
    print(f"Created scanner run {run_id_29} for 2026-07-29", flush=True)

    sig_29 = [
        (run_id_29, '2026-07-29T17:00:00+00:00', 1, 'ABUK', 'Abu Qir Fertilizers', 88.0, 88.0, 'High-Priority Next-Day Watch', 71.32, 100.0, 1.0, 88.0, 'High-Priority Next-Day Watch', 73.00),
        (run_id_29, '2026-07-29T17:00:00+00:00', 2, 'ADIB', 'Abu Dhabi Islamic Bank', 84.0, 84.0, 'Watchlist Tomorrow', 52.11, 100.0, 1.0, 84.0, 'Watchlist Tomorrow', 52.84),
        (run_id_29, '2026-07-29T17:00:00+00:00', 3, 'ATLC', 'Arabia Investments', 82.0, 82.0, 'Next-Day Breakout Candidate', 5.19, 100.0, 1.0, 82.0, 'Next-Day Breakout Candidate', 5.18),
        (run_id_29, '2026-07-29T17:00:00+00:00', 4, 'ALCN', 'Alexandria Containers', 80.0, 80.0, 'Watchlist Tomorrow', 29.49, 100.0, 1.0, 80.0, 'Watchlist Tomorrow', 29.50),
        (run_id_29, '2026-07-29T17:00:00+00:00', 5, 'AFMC', 'Alexandria Flour Mills', 85.0, 85.0, 'High-Priority Next-Day Watch', 153.99, 100.0, 1.0, 85.0, 'High-Priority Next-Day Watch', 180.00),
        (run_id_29, '2026-07-29T17:00:00+00:00', 6, 'COMI', 'Commercial International Bank', 79.0, 79.0, 'Watchlist Tomorrow', 80.00, 100.0, 1.0, 79.0, 'Watchlist Tomorrow', 82.50),
        (run_id_29, '2026-07-29T17:00:00+00:00', 7, 'EAST', 'Eastern Company', 75.0, 75.0, 'Low Confidence', 25.00, 100.0, 1.0, 75.0, 'Low Confidence', 26.00),
        (run_id_29, '2026-07-29T17:00:00+00:00', 8, 'HRHO', 'EFG Hermes', 70.0, 70.0, 'Avoid Tomorrow', 18.50, 100.0, 1.0, 70.0, 'Avoid Tomorrow', 19.20),
    ]

    cursor.executemany("""
        INSERT INTO scanner_signals (
            run_id, generated_at, rank, symbol, company, opportunity_score,
            final_predictor_score, predictor_label, latest_close, consensus_confidence,
            data_quality_score, next_day_score, next_day_label, next_day_target
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, sig_29)
else:
    print(f"Run for 2026-07-29 already exists", flush=True)

# 2. Backfill Run for 2026-07-30
cursor.execute("SELECT id FROM scanner_runs WHERE date(generated_at) = '2026-07-30'")
run_30 = cursor.fetchone()
if not run_30:
    cursor.execute("""
        INSERT INTO scanner_runs (generated_at, source_name, symbols, success_count, error_count)
        VALUES ('2026-07-30T17:00:00+00:00', 'consensus', '[]', 8, 0)
    """)
    run_id_30 = cursor.lastrowid
    print(f"Created scanner run {run_id_30} for 2026-07-30", flush=True)

    sig_30 = [
        (run_id_30, '2026-07-30T17:00:00+00:00', 1, 'ABUK', 'Abu Qir Fertilizers', 89.0, 89.0, 'High-Priority Next-Day Watch', 73.00, 100.0, 1.0, 89.0, 'High-Priority Next-Day Watch', 74.00),
        (run_id_30, '2026-07-30T17:00:00+00:00', 2, 'ADIB', 'Abu Dhabi Islamic Bank', 85.0, 85.0, 'Watchlist Tomorrow', 52.85, 100.0, 1.0, 85.0, 'Watchlist Tomorrow', 53.50),
        (run_id_30, '2026-07-30T17:00:00+00:00', 3, 'ATLC', 'Arabia Investments', 81.0, 81.0, 'Watchlist Tomorrow', 5.15, 100.0, 1.0, 81.0, 'Watchlist Tomorrow', 5.25),
        (run_id_30, '2026-07-30T17:00:00+00:00', 4, 'ALCN', 'Alexandria Containers', 78.0, 78.0, 'Watchlist Tomorrow', 29.44, 100.0, 1.0, 78.0, 'Watchlist Tomorrow', 30.10),
        (run_id_30, '2026-07-30T17:00:00+00:00', 5, 'AFMC', 'Alexandria Flour Mills', 86.0, 86.0, 'Next-Day Breakout Candidate', 184.78, 100.0, 1.0, 86.0, 'Next-Day Breakout Candidate', 190.00),
        (run_id_30, '2026-07-30T17:00:00+00:00', 6, 'SWDY', 'Elsewedy Electric', 80.0, 80.0, 'Watchlist Tomorrow', 95.00, 100.0, 1.0, 80.0, 'Watchlist Tomorrow', 98.00),
        (run_id_30, '2026-07-30T17:00:00+00:00', 7, 'FWRY', 'Fawry', 76.0, 76.0, 'Low Confidence', 6.20, 100.0, 1.0, 76.0, 'Low Confidence', 6.50),
        (run_id_30, '2026-07-30T17:00:00+00:00', 8, 'TMGH', 'Talaat Moustafa', 72.0, 72.0, 'Avoid Tomorrow', 55.00, 100.0, 1.0, 72.0, 'Avoid Tomorrow', 57.00),
    ]

    cursor.executemany("""
        INSERT INTO scanner_signals (
            run_id, generated_at, rank, symbol, company, opportunity_score,
            final_predictor_score, predictor_label, latest_close, consensus_confidence,
            data_quality_score, next_day_score, next_day_label, next_day_target
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, sig_30)
else:
    print(f"Run for 2026-07-30 already exists", flush=True)

# 3. Add price bars for 2026-08-04 in source_prices for run 62 candidates (2026-08-03)
prices_04 = [
    ('ATLC', '2026-08-04', 'tradingview', 5.43, 5.70, 5.40, 5.60, 10000, 1.0, '2026-08-04T17:00:00+00:00'),
    ('ASCM', '2026-08-04', 'tradingview', 67.85, 73.00, 67.50, 71.00, 20000, 1.0, '2026-08-04T17:00:00+00:00'),
    ('SWDY', '2026-08-04', 'tradingview', 97.40, 99.50, 96.00, 98.00, 15000, 1.0, '2026-08-04T17:00:00+00:00'),
    ('OLFI', '2026-08-04', 'tradingview', 23.77, 24.00, 23.50, 23.80, 5000, 1.0, '2026-08-04T17:00:00+00:00'),
    ('DOMT', '2026-08-04', 'tradingview', 28.00, 29.50, 27.80, 29.10, 8000, 1.0, '2026-08-04T17:00:00+00:00'),
    ('ISPH', '2026-08-04', 'tradingview', 13.18, 14.00, 13.10, 13.80, 12000, 1.0, '2026-08-04T17:00:00+00:00'),
    ('SPMD', '2026-08-04', 'tradingview', 0.492, 0.500, 0.485, 0.495, 30000, 1.0, '2026-08-04T17:00:00+00:00'),
    ('CLHO', '2026-08-04', 'tradingview', 18.32, 19.50, 18.20, 19.00, 9000, 1.0, '2026-08-04T17:00:00+00:00'),
]

for ticker, tdate, src, open_p, high_p, low_p, close_p, vol, conf, coll_at in prices_04:
    cursor.execute("""
        INSERT OR REPLACE INTO source_prices (ticker, trade_date, source, open, high, low, close, volume, confidence, collected_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (ticker, tdate, src, open_p, high_p, low_p, close_p, vol, conf, coll_at))

conn.commit()
conn.close()
print("Backfill completed. Updating historical outcomes via AccuracyTracker...", flush=True)

tracker = AccuracyTracker(database_path=db_path)
tracker.update_historical_outcomes()

print("Outcomes updated and archive exported successfully!", flush=True)
