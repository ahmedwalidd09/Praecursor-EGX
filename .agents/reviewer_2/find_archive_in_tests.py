import glob, re

for f in glob.glob("tests/**/*.py", recursive=True):
    content = open(f, encoding="utf-8").read()
    if "accuracy_history_archive" in content or "export_accuracy_history_archive" in content:
        print(f"Found in test file: {f}")
