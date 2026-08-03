import sqlite3
import os
import sys

db_paths = ['database/praecursor.db', 'data/signal_history.db', 'signal_history.db', 'data/scanner.db', 'reports/signal_history.db']

for p in db_paths:
    if os.path.exists(p):
        print(f"=== DB: {p} (size: {os.path.getsize(p)} bytes) ===", flush=True)
        try:
            conn = sqlite3.connect(p)
            cursor = conn.cursor()
            tables = [t[0] for t in cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
            print(f"Tables: {tables}", flush=True)
            for t in tables:
                cnt = cursor.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                print(f"  Table '{t}': {cnt} rows", flush=True)
                cols = [c[1] for c in cursor.execute(f"PRAGMA table_info({t})").fetchall()]
                print(f"    Columns: {cols}", flush=True)
                if cnt > 0 and cnt <= 20:
                    rows = cursor.execute(f"SELECT * FROM {t}").fetchall()
                    print("    Rows:", flush=True)
                    for r in rows:
                        print("      ", r, flush=True)
                elif cnt > 20:
                    rows = cursor.execute(f"SELECT * FROM {t} LIMIT 3").fetchall()
                    print("    Sample 3 rows:", flush=True)
                    for r in rows:
                        print("      ", r, flush=True)
            conn.close()
        except Exception as e:
            print(f"Error reading {p}: {e}", flush=True)
    else:
        print(f"=== DB: {p} DOES NOT EXIST ===", flush=True)
