import csv
import sqlite3
from pathlib import Path

db_path = Path("database/praecursor.db")
csv_path = Path("reports/archive/accuracy_history_archive.csv")

print("=== 1. AUDIT OF CSV ARCHIVE FILE ===")
if not csv_path.exists():
    print(f"CSV file does NOT exist at {csv_path}")
else:
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
    print(f"Total rows in CSV: {len(reader)}")
    
    dates = {}
    duplicates = []
    seen_keys = set()
    
    for idx, row in enumerate(reader):
        s_date = row["signal_date"]
        run_id = row["run_id"]
        symbol = row["symbol"]
        hit = row["next_day_hit"]
        cum_total = row["cumulative_total"]
        cum_hits = row["cumulative_hits"]
        cum_acc = row["cumulative_accuracy_pct"]
        
        dates[s_date] = dates.get(s_date, 0) + 1
        key = (s_date, symbol)
        if key in seen_keys:
            duplicates.append((idx + 2, key))
        seen_keys.add(key)
    
    print("Record count per signal_date in CSV:")
    for d, cnt in sorted(dates.items()):
        print(f"  {d}: {cnt} records")
    print(f"Duplicate (signal_date, symbol) pairs: {len(duplicates)}")
    for d in duplicates:
        print(f"  Line {d[0]}: {d[1]}")

print("\n=== 2. AUDIT OF SQLITE DATABASE ===")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

print("\n--- scanner_runs ---")
runs = conn.execute("SELECT id, generated_at, date(generated_at) as run_date FROM scanner_runs ORDER BY id ASC").fetchall()
print(f"Total scanner_runs: {len(runs)}")
run_dates = {}
for r in runs:
    rd = r["run_date"]
    run_dates[rd] = run_dates.get(rd, []) + [r["id"]]

for rd, r_ids in sorted(run_dates.items()):
    print(f"  Date {rd}: {len(r_ids)} runs (IDs {min(r_ids)}..{max(r_ids)}) -> Max Run ID: {max(r_ids)}")

print("\n--- scanner_signals per Max Run ID per date ---")
max_runs = conn.execute("""
    SELECT MAX(id) as max_run_id, date(generated_at) as run_date
    FROM scanner_runs
    GROUP BY date(generated_at)
    ORDER BY run_date ASC
""").fetchall()

for mr in max_runs:
    r_id = mr["max_run_id"]
    r_date = mr["run_date"]
    top8 = conn.execute("""
        SELECT rank, symbol, latest_close, next_day_target, next_day_label
        FROM scanner_signals
        WHERE run_id = ?
        ORDER BY rank ASC
        LIMIT 8
    """, (r_id,)).fetchall()
    print(f"  Run Date {r_date} (Max Run ID {r_id}): Top 8 count = {len(top8)}")
    for s in top8:
        print(f"    Rank {s['rank']}: {s['symbol']} | Close={s['latest_close']} | Target={s['next_day_target']}")

print("\n--- scanner_signal_outcomes in DB ---")
outcomes = conn.execute("SELECT id, run_id, symbol, signal_date, next_day_hit, next_day_return, next_day_max_return FROM scanner_signal_outcomes ORDER BY id ASC").fetchall()
print(f"Total outcome rows in DB: {len(outcomes)}")
out_dates = {}
for o in outcomes:
    sd = o["signal_date"]
    out_dates[sd] = out_dates.get(sd, 0) + 1
for sd, cnt in sorted(out_dates.items()):
    print(f"  Signal Date {sd}: {cnt} outcomes in DB")

print("\n--- Source Prices Date Range ---")
sp_dates = conn.execute("SELECT MIN(trade_date), MAX(trade_date), COUNT(DISTINCT trade_date) FROM source_prices").fetchone()
print(f"Source prices trade dates range: {sp_dates[0]} to {sp_dates[1]} ({sp_dates[2]} total trade dates)")

conn.close()
