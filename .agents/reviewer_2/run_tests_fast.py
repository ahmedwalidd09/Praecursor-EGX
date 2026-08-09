import subprocess
import sys
from pathlib import Path

root = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX")
print("Running pytest tests...")
sys.stdout.flush()

res = subprocess.run(
    [sys.executable, "-m", "pytest", "tests", "-v", "--tb=short"],
    cwd=root,
    capture_output=True,
    text=True,
    timeout=120
)

out_file = root / ".agents" / "reviewer_2" / "test_results.txt"
with open(out_file, "w", encoding="utf-8") as f:
    f.write(f"EXIT CODE: {res.returncode}\n\n")
    f.write("=== STDOUT ===\n")
    f.write(res.stdout)
    f.write("\n=== STDERR ===\n")
    f.write(res.stderr)

print(f"DONE. Return code: {res.returncode}")
