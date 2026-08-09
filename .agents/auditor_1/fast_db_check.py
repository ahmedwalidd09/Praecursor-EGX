import sqlite3
import csv
from pathlib import Path

project_root = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX")
db_path = project_root / "database" / "praecursor.db"
archive_path = project_root / "reports" / "archive" / "accuracy_history_archive.csv"
out_file = project_root / ".agents" / "auditor_1" / "fast_db_report.txt"

content = []

if db_path.exists():
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    content.append(f"Tables: {tables}")

    runs = c.execute("SELECT id, generated_at FROM scanner_runs").fetchall()
    content.append(f"Total scanner_runs: {len(runs)}")
    for r in runs:
        content.append(f"  Run ID: {r['id']}, Generated: {r['generated_at']}")

    sig_cnt = c.execute("SELECT count(*) FROM scanner_signals").fetchone()[0]
    content.append(f"Total scanner_signals: {sig_cnt}")

    outcomes = c.execute("SELECT * FROM scanner_signal_outcomes").fetchall()
    content.append(f"Total scanner_signal_outcomes: {len(outcomes)}")
    for o in outcomes[:15]:
        content.append(f"  Outcome: run_id={o['run_id']}, symbol={o['symbol']}, signal_date={o['signal_date']}, hit={o['next_day_hit']}, return={o['next_day_return']}")

    prices_cnt = c.execute("SELECT count(*) FROM source_prices").fetchone()[0]
    content.append(f"Total source_prices: {prices_cnt}")

    conn.close()

if archive_path.exists():
    with open(archive_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        content.append(f"\nCSV Archive Total Rows: {len(rows)}")
        for r in rows[:15]:
            content.append(f"  CSV Row: signal_date={r['signal_date']}, run_id={r['run_id']}, symbol={r['symbol']}, hit={r['next_day_hit']}, cum_total={r['cumulative_total']}, cum_hits={r['cumulative_hits']}, cum_acc={r['cumulative_accuracy_pct']}")

out_file.write_text("\n".join(content), encoding="utf-8")
print("FAST DB CHECK COMPLETE")
