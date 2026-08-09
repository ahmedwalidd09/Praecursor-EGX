import sqlite3
import os
import sys

db_paths = [
    "database/praecursor.db",
    "data/scanner.db",
    "data/signal_history.db",
    "config/praecursor.db"
]

for db_path in db_paths:
    if not os.path.exists(db_path):
        print(f"DB does not exist: {db_path}", flush=True)
        continue
    print(f"\n================ DB: {db_path} ================", flush=True)
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        tables = [row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        print("Tables:", tables, flush=True)
        for t in tables:
            cnt = cur.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            print(f"  Table '{t}': {cnt} rows", flush=True)
            
            if t == "scanner_runs":
                runs = cur.execute("SELECT id, generated_at, date(generated_at) as run_date FROM scanner_runs").fetchall()
                for r in runs:
                    print("    Run:", dict(r), flush=True)
            elif t == "scanner_signals":
                sig_counts = cur.execute("SELECT run_id, count(*) as cnt FROM scanner_signals GROUP BY run_id").fetchall()
                for sc in sig_counts:
                    print("    Signals count:", dict(sc), flush=True)
            elif t == "scanner_signal_outcomes":
                outcomes = cur.execute("SELECT signal_date, run_id, count(*) as cnt FROM scanner_signal_outcomes GROUP BY signal_date, run_id").fetchall()
                print("    Outcomes grouped by date/run:", [dict(o) for o in outcomes], flush=True)
            elif t == "source_prices":
                dates = cur.execute("SELECT DISTINCT trade_date FROM source_prices ORDER BY trade_date DESC LIMIT 15").fetchall()
                print("    Recent source_prices trade_dates:", [d[0] for d in dates], flush=True)
    except Exception as e:
        print("Error reading db:", e, flush=True)
