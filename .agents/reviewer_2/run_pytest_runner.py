import subprocess
from pathlib import Path

root = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX")
res = subprocess.run(["pytest", "tests"], cwd=root, capture_output=True, text=True)

out_file = root / ".agents" / "reviewer_2" / "pytest_results.txt"
with open(out_file, "w", encoding="utf-8") as f:
    f.write(f"EXIT CODE: {res.returncode}\n")
    f.write("=== STDOUT ===\n")
    f.write(res.stdout)
    f.write("\n=== STDERR ===\n")
    f.write(res.stderr)

print(f"Pytest finished with returncode {res.returncode}. Output written to {out_file}")
