import sqlite3
import csv
from pathlib import Path

project_root = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX")
db_path = project_root / "database" / "praecursor.db"
archive_path = project_root / "reports" / "archive" / "accuracy_history_archive.csv"
out_file = project_root / ".agents" / "auditor_1" / "db_results.txt"

with open(out_file, "w", encoding="utf-8") as out:
    out.write(f"=== DATABASE AUDIT REPORT ===\n")
    out.write(f"DB Path: {db_path}\n")
    out.write(f"DB Exists: {db_path.exists()}\n\n")

    if db_path.exists():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        out.write(f"Tables: {tables}\n\n")

        for t in tables:
            cnt = c.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            out.write(f"Table '{t}': {cnt} rows\n")

        out.write("\n--- scanner_runs ---\n")
        runs = c.execute("SELECT * FROM scanner_runs").fetchall()
        for r in runs:
            out.write(f"{dict(r)}\n")

        out.write("\n--- scanner_signals count per run_id ---\n")
        sig_counts = c.execute("SELECT run_id, count(*) as c FROM scanner_signals GROUP BY run_id").fetchall()
        for r in sig_counts:
            out.write(f"run_id {r['run_id']}: {r['c']} signals\n")

        out.write("\n--- scanner_signal_outcomes ---\n")
        outcomes = c.execute("SELECT * FROM scanner_signal_outcomes").fetchall()
        out.write(f"Total outcome rows: {len(outcomes)}\n")
        for r in outcomes:
            out.write(f"{dict(r)}\n")

        out.write("\n--- source_prices ---\n")
        prices_cnt = c.execute("SELECT count(*) FROM source_prices").fetchone()[0]
        out.write(f"Total source_prices rows: {prices_cnt}\n")

        conn.close()

    out.write(f"\n=== CSV ARCHIVE AUDIT ===\n")
    out.write(f"CSV Path: {archive_path}\n")
    out.write(f"CSV Exists: {archive_path.exists()}\n")

    if archive_path.exists():
        with open(archive_path, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
            out.write(f"CSV Total Rows: {len(reader)}\n")
            for idx, row in enumerate(reader):
                out.write(f"Row {idx+1}: {row}\n")

print("Finished writing report")
