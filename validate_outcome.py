import sys
sys.path.insert(0, r'C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\src')
from tvDatafeed import TvDatafeed, Interval
import pandas as pd

symbols = ['UEFM', 'CEFM', 'EGAS', 'MILS', 'GSSC', 'EALR', 'KWIN', 'UNIT']
prev_closes = {'UEFM': 546.25, 'CEFM': 136.00, 'EGAS': 58.55, 'MILS': 198.00, 'GSSC': 275.00, 'EALR': 377.76, 'KWIN': 87.50, 'UNIT': 17.81}
targets = {'UEFM': 564.88, 'CEFM': 141.00, 'EGAS': 61.77, 'MILS': 213.86, 'GSSC': 281.09, 'EALR': 398.62, 'KWIN': 94.34, 'UNIT': 18.78}
stops = {'UEFM': 536.97, 'CEFM': 131.57, 'EGAS': 56.94, 'MILS': 198.07, 'GSSC': 270.46, 'EALR': 367.33, 'KWIN': 84.09, 'UNIT': 17.32}

results = []
for sym in symbols:
    df = None
    for attempt in range(3):
        try:
            tv = TvDatafeed()
            df = tv.get_hist(sym, 'EGX', interval=Interval.in_daily, n_bars=3)
            if df is not None and len(df) >= 1:
                break
        except Exception as e:
            pass
    
    if df is not None and len(df) >= 1:
        today = df.iloc[-1]
        high = float(today['high'])
        low = float(today['low'])
        close = float(today['close'])
        date_str = str(df.index[-1])
        prev = prev_closes[sym]
        tgt = targets[sym]
        stp = stops[sym]
        hit_target = high >= tgt
        hit_stop = low <= stp
        change_pct = (close - prev) / prev * 100
        if hit_target:
            outcome = 'TARGET HIT'
        elif hit_stop:
            outcome = 'STOP HIT'
        elif close > prev:
            outcome = 'UP (no target)'
        else:
            outcome = 'DOWN (no stop)'
        results.append({
            'symbol': sym, 
            'date': date_str,
            'high': high, 
            'low': low, 
            'close': close, 
            'change_pct': round(change_pct, 2), 
            'target': tgt, 
            'stop': stp, 
            'outcome': outcome
        })
    else:
        results.append({'symbol': sym, 'error': 'No data returned'})

import json
print(json.dumps(results, indent=2))
