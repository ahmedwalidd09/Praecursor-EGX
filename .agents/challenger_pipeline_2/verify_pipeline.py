import os
import sys
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX")
DB_PATH = PROJECT_ROOT / "database" / "praecursor.db"
DB_BAK = PROJECT_ROOT / "database" / "praecursor.db.bak"

def run_cmd(cmd, cwd=PROJECT_ROOT):
    print(f"=== RUNNING: {' '.join(cmd)} ===")
    res = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    print(f"Return Code: {res.returncode}")
    print("--- STDOUT ---")
    print(res.stdout.strip())
    print("--- STDERR ---")
    print(res.stderr.strip())
    print("===========================================\n")
    return res

def test_regenerate_dashboard():
    print("--- TEST 1: regenerate_dashboard.py ---")
    res = run_cmd([sys.executable, "tools/regenerate_dashboard.py"])
    return res.returncode == 0 and "Traceback" not in res.stderr

def test_missing_db():
    print("--- TEST 3: Pipeline stability with missing praecursor.db ---")
    db_existed = DB_PATH.exists()
    if db_existed:
        if DB_BAK.exists():
            os.remove(DB_BAK)
        shutil.move(DB_PATH, DB_BAK)
        print(f"Moved {DB_PATH} to {DB_BAK}")
    
    try:
        res = run_cmd([sys.executable, "tools/regenerate_dashboard.py"])
        success = (res.returncode == 0)
    finally:
        if db_existed and DB_BAK.exists():
            if DB_PATH.exists():
                os.remove(DB_PATH)
            shutil.move(DB_BAK, DB_PATH)
            print(f"Restored {DB_PATH}")
    return success

def test_network_isolation():
    print("--- TEST 4: Network isolation unit test ---")
    res = run_cmd([sys.executable, "-m", "pytest", "tests/test_network_isolation.py"])
    return res.returncode == 0

def test_full_pytest_suite():
    print("--- TEST 4b: Full pytest suite ---")
    res = run_cmd([sys.executable, "-m", "pytest", "tests/"])
    return res

if __name__ == "__main__":
    t1 = test_regenerate_dashboard()
    t3 = test_missing_db()
    t4 = test_network_isolation()
    t4b = test_full_pytest_suite()
    print("SUMMARY RESULTS:")
    print(f"Test 1 (Regenerate Dashboard): {'PASS' if t1 else 'FAIL'}")
    print(f"Test 3 (Missing DB Stability): {'PASS' if t3 else 'FAIL'}")
    print(f"Test 4a (Network Isolation Guard Test): {'PASS' if t4 else 'FAIL'}")
    print(f"Test 4b (Full Pytest Suite Return Code): {t4b.returncode}")
