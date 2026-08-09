import sqlite3
import csv
from pathlib import Path

root = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX")
db_file = root / "database" / "praecursor.db"
csv_file = root / "reports" / "archive" / "accuracy_history_archive.csv"

out_path = root / ".agents" / "auditor_1" / "db_audit_output.txt"
lines = []

lines.append("=== DB AUDIT FOR DATABASE/PRAECURSOR.DB ===")
if db_file.exists():
    conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Query scanner_runs
    runs = c.execute("SELECT id, generated_at FROM scanner_runs ORDER BY id ASC").fetchall()
    lines.append(f"Total scanner_runs: {len(runs)}")
    for r in runs:
        lines.append(f"  Run {r['id']}: {r['generated_at']}")

    # Query scanner_signal_outcomes
    outcomes = c.execute("SELECT * FROM scanner_signal_outcomes ORDER BY signal_date ASC, run_id ASC, id ASC").fetchall()
    lines.append(f"\nTotal scanner_signal_outcomes: {len(outcomes)}")
    for o_row in outcomes:
        o = dict(o_row)
        lines.append(f"  Outcome: id={o.get('id')}, run_id={o.get('run_id')}, date={o.get('signal_date')}, symbol={o.get('symbol')}, hit={o.get('next_day_hit')}, ret={o.get('next_day_return')}, max_ret={o.get('next_day_max_return')}")

    # Top 8 signals per run
    signals_cnt = c.execute("SELECT count(*) FROM scanner_signals").fetchone()[0]
    lines.append(f"\nTotal scanner_signals: {signals_cnt}")

    conn.close()
else:
    lines.append("DB File NOT FOUND")

lines.append("\n=== CSV ARCHIVE AUDIT ===")
if csv_file.exists():
    with open(csv_file, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        lines.append(f"CSV Total Rows: {len(rows)}")
        for i, r in enumerate(rows):
            lines.append(f"  Row {i+1}: signal_date={r.get('signal_date')}, run_id={r.get('run_id')}, symbol={r.get('symbol')}, hit={r.get('next_day_hit')}, cum_total={r.get('cumulative_total')}, cum_hits={r.get('cumulative_hits')}, cum_acc={r.get('cumulative_accuracy_pct')}")
else:
    lines.append("CSV File NOT FOUND")

out_path.write_text("\n".join(lines), encoding="utf-8")
print("DONE WRITING DB AUDIT OUTPUT")
