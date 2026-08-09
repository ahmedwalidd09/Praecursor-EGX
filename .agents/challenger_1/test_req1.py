import subprocess
import sys
from pathlib import Path

root = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX")
script = root / "tools" / "run_autonomous_pipeline.py"

print("=== Test 1A: Non-trading day manual trigger (--date 2026-08-07) ===")
res1 = subprocess.run([sys.executable, str(script), "--date", "2026-08-07"], capture_output=True, text=True, cwd=str(root))
print("Exit Code:", res1.returncode)
print("Stdout:\n", res1.stdout)
assert res1.returncode == 0, f"Expected returncode 0, got {res1.returncode}"
assert "SKIPPED: Non-trading day" in res1.stdout, "Expected 'SKIPPED: Non-trading day' in stdout"
print("Test 1A PASSED!\n")

print("=== Test 1B: Forced execution manual trigger (--date 2026-08-07 --force --dry-run-telegram) ===")
# Note: --force will run all 4 stages. We use --dry-run-telegram so it won't send real telegram messages.
res2 = subprocess.run([sys.executable, str(script), "--date", "2026-08-07", "--force", "--dry-run-telegram"], capture_output=True, text=True, cwd=str(root))
print("Exit Code:", res2.returncode)
print("Stdout snippet:\n", res2.stdout[:500])
assert "PROCESSING: Forced execution" in res2.stdout, "Expected 'PROCESSING: Forced execution' in stdout"
print("Test 1B PASSED!\n")
