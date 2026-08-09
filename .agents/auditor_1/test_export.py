from praecursor.analysis.accuracy_tracker import AccuracyTracker
from pathlib import Path
import csv

tracker = AccuracyTracker()
exported = tracker.export_accuracy_history_archive()

print("Exported to:", exported)

with open(exported, "r", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
    print(f"CSV Total Rows after export: {len(rows)}")
    for r in rows:
        print(f"  Row: signal_date={r.get('signal_date')}, run_id={r.get('run_id')}, symbol={r.get('symbol')}, hit={r.get('next_day_hit')}, cum_total={r.get('cumulative_total')}, cum_hits={r.get('cumulative_hits')}, cum_acc={r.get('cumulative_accuracy_pct')}")
