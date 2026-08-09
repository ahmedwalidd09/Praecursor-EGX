import csv
from pathlib import Path

root = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX")
csv_path = root / "reports" / "archive" / "accuracy_history_archive.csv"

print("=== Test 3: Verifying reports/archive/accuracy_history_archive.csv ===")
assert csv_path.exists(), f"CSV archive file not found at {csv_path}"

with open(csv_path, mode="r", encoding="utf-8") as f:
    reader = list(csv.DictReader(f))

print(f"Total Rows Parsed: {len(reader)}")
assert len(reader) == 40, f"Expected exactly 40 records, got {len(reader)}"

by_date = {}
expected_headers = [
    "signal_date", "run_id", "symbol", "latest_close", "next_day_target",
    "next_day_label", "next_day_hit", "next_day_return", "next_day_max_return",
    "cumulative_total", "cumulative_hits", "cumulative_accuracy_pct"
]

running_total = 0
running_hits = 0

for idx, row in enumerate(reader, start=1):
    # Verify expected headers present
    for h in expected_headers:
        assert h in row, f"Missing header '{h}' in row {idx}"

    s_date = row["signal_date"]
    by_date[s_date] = by_date.get(s_date, 0) + 1

    hit = int(row["next_day_hit"])
    assert hit in (0, 1), f"Row {idx}: next_day_hit must be 0 or 1, got {hit}"

    running_total += 1
    if hit == 1:
        running_hits += 1

    cum_total = int(row["cumulative_total"])
    cum_hits = int(row["cumulative_hits"])
    cum_acc = float(row["cumulative_accuracy_pct"])

    assert cum_total == running_total, f"Row {idx}: cumulative_total expected {running_total}, got {cum_total}"
    assert cum_hits == running_hits, f"Row {idx}: cumulative_hits expected {running_hits}, got {cum_hits}"

    expected_acc = round((running_hits / running_total) * 100.0, 2)
    assert abs(cum_acc - expected_acc) < 0.01, f"Row {idx}: cumulative_accuracy_pct expected {expected_acc}, got {cum_acc}"

    # Verify numbers are valid floats
    float(row["latest_close"])
    float(row["next_day_target"])
    float(row["next_day_return"])
    float(row["next_day_max_return"])
    assert len(row["symbol"]) > 0, f"Row {idx}: symbol empty"
    assert len(row["next_day_label"]) > 0, f"Row {idx}: next_day_label empty"

print("\n--- Daily Record Counts ---")
for d, count in sorted(by_date.items()):
    print(f"  Date {d}: {count} records")
    assert count == 8, f"Expected 8 records for date {d}, got {count}"

assert len(by_date) == 5, f"Expected 5 unique signal dates, got {len(by_date)}"

print("\nCumulative Stats Summary:")
print(f"  Total Records: {running_total}")
print(f"  Total Hits: {running_hits}")
print(f"  Final Accuracy %: {expected_acc}%")

print("\nTest 3 PASSED PERFECTLY!")
