import sqlite3

db_path = r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\database\praecursor.db"
print("Connecting to:", db_path)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", [t[0] for t in tables])

for t in [t[0] for t in tables]:
    cnt = cur.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    print(f"  {t}: {cnt} rows")

print("\nChecking scanner_runs dates:")
runs = cur.execute("SELECT id, generated_at, date(generated_at) as run_date FROM scanner_runs ORDER BY id").fetchall()
for r in runs:
    print("  Run:", r)

print("\nChecking scanner_signal_outcomes count per signal_date:")
outcomes = cur.execute("SELECT signal_date, count(*), sum(next_day_hit) FROM scanner_signal_outcomes GROUP BY signal_date").fetchall()
for o in outcomes:
    print("  Outcome date:", o)

conn.close()
