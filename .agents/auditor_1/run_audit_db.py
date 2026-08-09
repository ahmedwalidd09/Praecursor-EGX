import sqlite3
import csv
from pathlib import Path

project_root = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX")
db_path = project_root / "database" / "praecursor.db"
archive_path = project_root / "reports" / "archive" / "accuracy_history_archive.csv"
out_file = project_root / ".agents" / "auditor_1" / "db_report.txt"

lines = []

lines.append(f"Checking Database: {db_path}")
if not db_path.exists():
    lines.append("Database file NOT FOUND!")
else:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    lines.append(f"Tables in database: {tables}")

    for t in ["scanner_runs", "scanner_signals", "scanner_signal_outcomes", "source_prices"]:
        if t in tables:
            cnt = cursor.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            lines.append(f"Table {t}: {cnt} rows")
        else:
            lines.append(f"Table {t}: NOT FOUND")

    if "scanner_signal_outcomes" in tables:
        cnt = cursor.execute("SELECT COUNT(*) FROM scanner_signal_outcomes").fetchone()[0]
        lines.append(f"\nTotal rows in scanner_signal_outcomes: {cnt}")
        rows = cursor.execute("SELECT * FROM scanner_signal_outcomes LIMIT 10").fetchall()
        lines.append("--- First 10 rows of scanner_signal_outcomes ---")
        for r in rows:
            lines.append(str(dict(r)))

    if "scanner_runs" in tables:
        runs = cursor.execute("SELECT * FROM scanner_runs ORDER BY id DESC LIMIT 10").fetchall()
        lines.append("\n--- Recent scanner_runs ---")
        for r in runs:
            lines.append(str(dict(r)))

    conn.close()

lines.append(f"\nChecking CSV Archive: {archive_path}")
if not archive_path.exists():
    lines.append("Archive CSV NOT FOUND!")
else:
    with open(archive_path, mode="r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        lines.append(f"CSV Total Rows: {len(reader)}")
        if len(reader) > 0:
            lines.append(f"First row: {reader[0]}")
            lines.append(f"Last row: {reader[-1]}")

out_file.write_text("\n".join(lines), encoding="utf-8")
print(f"Report written to {out_file}")
