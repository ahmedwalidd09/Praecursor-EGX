import sys
import sqlite3
import pandas as pd
from datetime import datetime
from contextlib import closing
from praecursor.core.price_bar import PriceBar

c = sqlite3.connect('database/praecursor.db')
c.row_factory = sqlite3.Row

query = '''SELECT s.run_id, s.symbol, s.generated_at, s.latest_close, s.next_day_label, s.swing_label, s.swing_stop_loss FROM scanner_signals s LEFT JOIN scanner_signal_outcomes o ON s.run_id = o.run_id AND s.symbol = o.symbol WHERE o.id IS NULL OR (o.next_day_hit IS NULL OR (o.swing_hit IS NULL AND o.swing_label LIKE '%Swing%')) LIMIT 1'''
row = c.execute(query).fetchone()
print(dict(row))

symbol = row['symbol']
signal_date_str = row['generated_at']
try:
    signal_date = datetime.fromisoformat(signal_date_str.replace('Z', '+00:00')).date()
except ValueError:
    signal_date = datetime.fromisoformat(signal_date_str).date()
end_date = signal_date + pd.Timedelta(days=30)

query_bars = '''
    SELECT trade_date, MAX(high) as high, MIN(low) as low, AVG(close) as close
    FROM source_prices
    WHERE ticker = ? AND trade_date > ? AND trade_date <= ?
    GROUP BY trade_date
    ORDER BY trade_date ASC
'''

future_bars = []
rows = c.execute(query_bars, (symbol, signal_date.isoformat(), end_date.isoformat())).fetchall()
for r in rows:
    future_bars.append(PriceBar(
        timestamp=datetime.fromisoformat(r['trade_date']).date(),
        open=r['close'], high=r['high'], low=r['low'], close=r['close'], volume=0
    ))

print('Future bars:', len(future_bars))
