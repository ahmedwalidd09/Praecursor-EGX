import pandas as pd
import sqlite3
import glob
import os

# 1. Clean symbols.csv
df = pd.read_csv('config/symbols.csv')
original_count = len(df)
# Remove symbols that start with EGS AND length > 4 (to keep EGSA) OR contain OTC
to_remove = df[(df['egx_symbol'].str.startswith('EGS') & (df['egx_symbol'].str.len() > 4)) | df['egx_symbol'].str.contains('OTC', case=False) | df['company'].str.contains('OTC', case=False)]
removed_symbols = to_remove['egx_symbol'].tolist()
df = df[~df['egx_symbol'].isin(removed_symbols)]
df.to_csv('config/symbols.csv', index=False)
print(f'Removed {original_count - len(df)} symbols from symbols.csv: {removed_symbols}')

# 2. Clean Database
conn = sqlite3.connect('database/praecursor.db')
cursor = conn.cursor()

# Get actual symbols in DB starting with EGS and length > 4
cursor.execute("SELECT DISTINCT symbol FROM scanner_signals WHERE (symbol LIKE 'EGS%' AND length(symbol) > 4) OR symbol LIKE '%OTC%'")
db_symbols = [row[0] for row in cursor.fetchall()]
all_removed = list(set(removed_symbols + db_symbols))

if all_removed:
    placeholders = ','.join(['?'] * len(all_removed))
    
    cursor.execute(f'DELETE FROM scanner_signals WHERE symbol IN ({placeholders})', all_removed)
    print(f'Deleted {cursor.rowcount} rows from scanner_signals')
    
    cursor.execute(f'DELETE FROM scanner_signal_outcomes WHERE symbol IN ({placeholders})', all_removed)
    print(f'Deleted {cursor.rowcount} rows from scanner_signal_outcomes')
    
    try:
        cursor.execute(f'DELETE FROM price_consensus WHERE symbol IN ({placeholders})', all_removed)
        print(f'Deleted {cursor.rowcount} rows from price_consensus')
    except sqlite3.OperationalError:
        pass
        
    try:
        cursor.execute(f'DELETE FROM consensus_sources WHERE symbol IN ({placeholders})', all_removed)
        print(f'Deleted {cursor.rowcount} rows from consensus_sources')
    except sqlite3.OperationalError:
        pass

    conn.commit()
conn.close()

# 3. Clean Cache
cache_files = []
for sym in all_removed:
    files = glob.glob(f'.cache/symbols/*{sym}*.parquet')
    cache_files.extend(files)
    
for f in cache_files:
    try:
        os.remove(f)
    except Exception as e:
        print(f'Failed to remove {f}: {e}')
print(f'Removed {len(cache_files)} cached files.')
