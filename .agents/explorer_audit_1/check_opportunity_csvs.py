import glob
import os
import sqlite3

csvs = glob.glob("reports/archive/opportunity_ranking_*.csv")
print(f"Total opportunity_ranking CSV files: {len(csvs)}")

dates = set()
for c in csvs:
    fname = os.path.basename(c)
    # opportunity_ranking_YYYYMMDD_HHMMSS.csv
    parts = fname.split("_")
    if len(parts) >= 3:
        d_str = parts[2]
        if len(d_str) == 8:
            dates.add(f"{d_str[:4]}-{d_str[4:6]}-{d_str[6:8]}")

print("Opportunity ranking dates found:", sorted(list(dates)))
