import sqlite3
import glob

conn = sqlite3.connect('database/praecursor.db')
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT * FROM scanner_signal_outcomes").fetchall()
print(f"Total rows in scanner_signal_outcomes: {len(rows)}")
for r in rows:
    print(dict(r))

print("\n--- Checking scanner_runs count per date ---")
runs_by_date = conn.execute("SELECT date(generated_at) as run_date, count(*) as cnt, min(id) as min_id, max(id) as max_id FROM scanner_runs GROUP BY date(generated_at)").fetchall()
for r in runs_by_date:
    print(dict(r))

conn.close()

print("\n--- Checking CSV files in reports ---")
csv_files = glob.glob("reports/**/*.csv", recursive=True)
print("CSV files:", csv_files)
for c in csv_files[:10]:
    print(c)
