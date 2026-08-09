import sys
import sqlite3
from pathlib import Path

root = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX")
sys.path.insert(0, str(root / "src"))

from praecursor.analysis.accuracy_tracker import AccuracyTracker

db_path = root / "database" / "praecursor.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("--- scanner_signal_outcomes counts per signal_date ---")
counts = cur.execute("""
    SELECT signal_date, COUNT(*) as cnt, SUM(next_day_hit) as hits
    FROM scanner_signal_outcomes
    WHERE next_day_hit IS NOT NULL
    GROUP BY signal_date
    ORDER BY signal_date ASC
""").fetchall()

total_records = 0
total_hits = 0
for row in counts:
    total_records += row["cnt"]
    total_hits += (row["hits"] or 0)
    print(f"Date: {row['signal_date']} -> Records: {row['cnt']}, Hits: {row['hits']}")

print(f"Total Completed Evaluation Records across all dates: {total_records}")
print(f"Total Hits across all dates: {total_hits}")
print(f"Overall Accuracy: {(total_hits / total_records * 100.0):.2f}%")

conn.close()

# Now run export_accuracy_history_archive()
tracker = AccuracyTracker()
exported_path = tracker.export_accuracy_history_archive()
print("\nExported CSV path:", exported_path)

csv_content = exported_path.read_text(encoding="utf-8").strip().split("\n")
print(f"CSV Total Non-empty Lines: {len(csv_content)}")
print(f"CSV Record Count (excluding header): {len(csv_content) - 1}")

print("\n--- First 5 CSV Rows ---")
for line in csv_content[:6]:
    print(line)

print("\n--- Last 5 CSV Rows ---")
for line in csv_content[-5:]:
    print(line)
