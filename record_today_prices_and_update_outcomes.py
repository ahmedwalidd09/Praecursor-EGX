import sys
import sqlite3
from pathlib import Path
sys.path.insert(0, r'C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\src')

from praecursor.analysis.accuracy_tracker import AccuracyTracker

db_path = Path(r'C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\database\praecursor.db')

prices_20260810 = [
    ('UEFM', '2026-08-10', 'tradingview', 546.25, 550.00, 542.00, 546.03, 1396, 1.0, '2026-08-10 18:00:00'),
    ('CEFM', '2026-08-10', 'tradingview', 136.00, 138.00, 134.00, 134.81, 1000, 1.0, '2026-08-10 18:00:00'),
    ('EGAS', '2026-08-10', 'tradingview', 58.55, 60.75, 58.69, 59.20, 1000, 1.0, '2026-08-10 18:00:00'),
    ('MILS', '2026-08-10', 'tradingview', 198.00, 200.10, 187.00, 187.77, 1000, 1.0, '2026-08-10 18:00:00'),
    ('GSSC', '2026-08-10', 'tradingview', 275.00, 276.80, 273.00, 274.66, 1000, 1.0, '2026-08-10 18:00:00'),
    ('EALR', '2026-08-10', 'tradingview', 377.76, 392.00, 375.02, 384.23, 1000, 1.0, '2026-08-10 18:00:00'),
    ('KWIN', '2026-08-10', 'tradingview', 87.50, 94.40, 87.01, 93.10, 1000, 1.0, '2026-08-10 18:00:00'),
    ('UNIT', '2026-08-10', 'tradingview', 17.81, 18.22, 17.70, 17.79, 1000, 1.0, '2026-08-10 18:00:00'),
]

conn = sqlite3.connect(db_path)
with conn:
    conn.executemany("""
        INSERT OR REPLACE INTO source_prices (ticker, trade_date, source, open, high, low, close, volume, confidence, collected_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, prices_20260810)

print("Inserted 2026-08-10 prices into source_prices table.")

# Update historical outcomes
tracker = AccuracyTracker(database_path=db_path)
tracker.update_historical_outcomes()
print("Historical outcomes updated via AccuracyTracker.")
