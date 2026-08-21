from tvDatafeed import TvDatafeed, Interval
tv = TvDatafeed()

stocks = ['EALR', 'GBCO', 'SVCE', 'EGAS', 'RACC', 'BINV', 'CERA', 'AJWA']
targets = [404.81, 33.03, 9.64, 62.33, 10.36, 50.18, 1.36, 195.27]
prev_close = [384.23, 31.81, 9.39, 59.20, 10.14, 48.85, 1.32, 186.09]
stops = [373.94, 31.20, 9.26, 57.63, 10.03, 48.18, 1.30, 181.50]

from datetime import date

for i, sym in enumerate(stocks):
    try:
        df = tv.get_hist(symbol=sym, exchange='EGX', interval=Interval.in_daily, n_bars=5)
        if df is not None and not df.empty:
            for idx, row in df.iterrows():
                bar_date = idx.date() if hasattr(idx, 'date') else idx
                if str(bar_date) == '2026-08-11':
                    day_high = float(row['high'])
                    day_close = float(row['close'])
                    hit_target = 'YES' if day_high >= targets[i] else 'NO'
                    hit_stop = 'YES' if float(row['low']) <= stops[i] else 'NO'
                    pct_from_prev = ((day_high - prev_close[i]) / prev_close[i]) * 100
                    print(f'{sym}: High={day_high}, Close={day_close}, PrevClose={prev_close[i]}, Target={targets[i]}, HitTarget={hit_target}, HitStop={hit_stop}, HighGain={pct_from_prev:.2f}%')
                    break
            else:
                print(f'{sym}: No data for 2026-08-11')
        else:
            print(f'{sym}: No data returned')
    except Exception as e:
        print(f'{sym}: Error - {e}')
