import subprocess
import sys
from pathlib import Path

root = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX")

print("=== Running pytest tests/ (unit tests) ===")
res_unit = subprocess.run([sys.executable, "-m", "pytest", "tests", "--ignore=tests/e2e", "-v"], cwd=root, capture_output=True, text=True)

print("=== Running pytest tests/e2e/ (e2e tests) ===")
res_e2e = subprocess.run([sys.executable, "-m", "pytest", "tests/e2e", "-v"], cwd=root, capture_output=True, text=True)

summary_file = root / ".agents" / "reviewer_2" / "pytest_full_summary.txt"
with open(summary_file, "w", encoding="utf-8") as f:
    f.write("=== UNIT TESTS ===\n")
    f.write(f"Exit code: {res_unit.returncode}\n")
    f.write(res_unit.stdout)
    if res_unit.stderr:
        f.write("\nSTDERR:\n" + res_unit.stderr)
    f.write("\n\n=== E2E TESTS ===\n")
    f.write(f"Exit code: {res_e2e.returncode}\n")
    f.write(res_e2e.stdout)
    if res_e2e.stderr:
        f.write("\nSTDERR:\n" + res_e2e.stderr)

print(f"Summary written to {summary_file}")
