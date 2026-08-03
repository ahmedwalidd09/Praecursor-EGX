import csv
import json
import requests
from pathlib import Path

def fetch_tradingview_symbols():
    url = 'https://scanner.tradingview.com/egypt/scan'
    payload = {
        'columns': ['name', 'description'],
        'range': [0, 500],  # Get up to 500 symbols
        'filter': [{'left': 'type', 'operation': 'in_range', 'right': ['stock', 'dr', 'fund']}]
    }
    print(f"Fetching from {url}...")
    res = requests.post(url, json=payload)
    if res.status_code != 200:
        raise RuntimeError(f"Failed to fetch symbols: {res.status_code} {res.text}")
    
    data = res.json()['data']
    print(f"Fetched {len(data)} symbols from TradingView.")
    return data

def main():
    root = Path(__file__).resolve().parents[1]
    symbols_csv_path = root / "config" / "symbols.csv"
    
    # Read existing symbols
    existing_symbols = set()
    rows = []
    with open(symbols_csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        for row in reader:
            existing_symbols.add(row['egx_symbol'].upper())
            rows.append(row)
            
    tv_data = fetch_tradingview_symbols()
    
    new_added = 0
    for item in tv_data:
        # TV format: "EGX:COMI", name is just "COMI"
        tv_symbol = item['d'][0].upper()
        # Sometimes there are weird suffixes, let's keep it clean
        if not tv_symbol.isalnum():
            # some might have numbers, just use as is
            pass
            
        if tv_symbol not in existing_symbols:
            # We'll map Yahoo suffix .CA, StockAnalysis same as symbol
            yahoo_sym = f"{tv_symbol}.CA"
            
            new_row = {
                'egx_symbol': tv_symbol,
                'company': item['d'][1],
                'yahoo_symbol': yahoo_sym,
                'stockanalysis_symbol': tv_symbol,
                'enabled': 'True',
            }
            if 'mubasher_symbol' in fieldnames:
                new_row['mubasher_symbol'] = tv_symbol
            if 'reason_disabled' in fieldnames:
                new_row['reason_disabled'] = ''
                
            rows.append(new_row)
            existing_symbols.add(tv_symbol)
            new_added += 1
            
    print(f"Adding {new_added} new symbols.")
    
    # Write back to CSV
    with open(symbols_csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            # Only write keys that are in fieldnames
            clean_row = {k: v for k, v in row.items() if k in fieldnames}
            writer.writerow(clean_row)
            
    print("Done!")

if __name__ == "__main__":
    main()
