import glob
import re

py_files = glob.glob("src/**/*.py", recursive=True)

keywords = ["next_day_target", "target_price", "is_solid_gain", "PriceConsensusEngine", "AccuracyTracker", "scanner_signal_outcomes"]

for f in py_files:
    try:
        with open(f, "r", encoding="utf-8") as fp:
            content = fp.read()
            for kw in keywords:
                if kw in content:
                    print(f"File {f} matches keyword '{kw}'")
    except Exception as e:
        pass
