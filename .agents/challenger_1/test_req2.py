import logging
import subprocess
import sys
from pathlib import Path

root = Path(r"C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX")
sys.path.insert(0, str(root))

from tools.run_autonomous_pipeline import run_stage, run_pipeline

logger = logging.getLogger("test_retry_logger")
logger.setLevel(logging.INFO)
stream_handler = logging.StreamHandler(sys.stdout)
logger.addHandler(stream_handler)

print("=== Test 2A: Unit Test for run_stage Retry Logic ===")
call_count = 0

def mock_subprocess_run(*args, **kwargs):
    global call_count
    call_count += 1
    class Result:
        returncode = 1 if call_count < 3 else 0
        stdout = f"Mock stdout attempt {call_count}"
        stderr = f"Mock stderr attempt {call_count}"
    return Result()

# Patch subprocess.run and time.sleep
import tools.run_autonomous_pipeline as pipeline_mod
original_run = subprocess.run
original_sleep = pipeline_mod.time.sleep

pipeline_mod.subprocess.run = mock_subprocess_run
pipeline_mod.time.sleep = lambda secs: print(f"[MockSleep] Slept {secs} seconds")

try:
    success = run_stage(
        logger=logger,
        stage_num=1,
        stage_name="Test Retry Stage",
        cmd=["mock", "command"],
        cwd=root,
        max_attempts=3,
        initial_backoff=0.01,
    )
    print("Stage Result:", success)
    print("Call Count:", call_count)
    assert success is True, "Stage should succeed on 3rd attempt"
    assert call_count == 3, f"Expected 3 attempts, got {call_count}"
    print("Test 2A PASSED!\n")

    print("=== Test 2B: Stage Fails All Retries ===")
    call_count = 0
    def mock_subprocess_run_fail(*args, **kwargs):
        global call_count
        call_count += 1
        class Result:
            returncode = 1
            stdout = "Error output"
            stderr = "Connection refused"
        return Result()

    pipeline_mod.subprocess.run = mock_subprocess_run_fail
    fail_success = run_stage(
        logger=logger,
        stage_num=1,
        stage_name="Failing Stage",
        cmd=["mock", "fail"],
        cwd=root,
        max_attempts=3,
        initial_backoff=0.01,
    )
    print("Fail Stage Result:", fail_success)
    print("Call Count:", call_count)
    assert fail_success is False, "Stage should return False after all retries fail"
    assert call_count == 3, f"Expected 3 attempts, got {call_count}"
    print("Test 2B PASSED!\n")

finally:
    pipeline_mod.subprocess.run = original_run
    pipeline_mod.time.sleep = original_sleep
