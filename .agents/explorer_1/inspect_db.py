import sqlite3
import os

p = 'reports/signal_history.db'
if os.path.exists(p):
    print(f"=== DB: {p} ===")
    conn = sqlite3.connect(p)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cursor.fetchall()]
    print("Tables:", tables)
    for t in tables:
        cursor.execute(f"SELECT count(*) FROM {t}")
        cnt = cursor.fetchone()[0]
        print(f"  {t}: {cnt} rows")
        if t in ["scanner_signal_outcomes", "scanner_signals", "signal_outcomes"]:
            cursor.execute(f"SELECT * FROM {t} LIMIT 20")
            rows = cursor.fetchall()
            print(f"  Sample {t} ({len(rows)}):")
            col_names = [d[0] for d in cursor.description]
            print("   Cols:", col_names)
            for row in rows:
                print("   ", row)
    conn.close()
