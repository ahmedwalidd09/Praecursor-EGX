import glob
import subprocess
import sys
from pathlib import Path

root = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX")
test_files = sorted(glob.glob("tests/**/test_*.py", recursive=True))

print(f"Found {len(test_files)} test files.")
sys.stdout.flush()

results = {}
for tf in test_files:
    timeout_sec = 60 if "tests\\e2e" in tf or "tests/e2e" in tf else 30
    try:
        res = subprocess.run(
            [sys.executable, "-m", "pytest", tf, "-q"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout_sec
        )
        if res.returncode == 0:
            status = "PASSED"
        else:
            status = f"FAILED (exit {res.returncode}): {res.stderr.strip() or res.stdout.strip()}"
    except subprocess.TimeoutExpired:
        status = f"TIMEOUT ({timeout_sec}s)"
    except Exception as e:
        status = f"ERROR: {e}"
    
    print(f"[{status}] {tf}", flush=True)
    results[tf] = status

summary_path = root / ".agents" / "reviewer_2" / "test_file_results.txt"
with open(summary_path, "w", encoding="utf-8") as f:
    for tf, st in results.items():
        f.write(f"{tf}: {st}\n")

print(f"Finished evaluating {len(test_files)} test files. Saved to {summary_path}", flush=True)
