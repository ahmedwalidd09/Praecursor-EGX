import csv
from pathlib import Path

csv_path = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\reports\archive\accuracy_history_archive.csv")
assert csv_path.exists(), f"File {csv_path} does not exist!"

with open(csv_path, mode="r", encoding="utf-8") as f:
    reader = list(csv.DictReader(f))

print(f"Total CSV records: {len(reader)}", flush=True)

# Group by signal_date
by_date = {}
for r in reader:
    d = r["signal_date"]
    by_date.setdefault(d, []).append(r)

print("Records per signal_date:", {d: len(rows) for d, rows in by_date.items()}, flush=True)

print("\nSample records (first 5 and last 5):", flush=True)
for r in reader[:5]:
    print(r, flush=True)
print("...")
for r in reader[-5:]:
    print(r, flush=True)

last_rec = reader[-1]
print(f"\nFinal cumulative total: {last_rec['cumulative_total']}, hits: {last_rec['cumulative_hits']}, accuracy_pct: {last_rec['cumulative_accuracy_pct']}%", flush=True)
