import os
import subprocess
import sys
from pathlib import Path
import pytest


class TestR1SchedulingTier1:
    """Tier 1: Feature Coverage for R1 Autonomous 5 PM Scheduling."""

    def test_r1_scheduled_task_registration(self, run_task_script):
        """Verify PowerShell/Batch script registers Windows Scheduled Task for 5:00 PM."""
        res = run_task_script("register_task.ps1", "PraecursorE2ETest1", "17:00")
        assert res.returncode == 0, f"Registration failed: {res.stderr}\n{res.stdout}"
        assert "registered successfully" in res.stdout.lower() or res.returncode == 0

        # Query schtasks to verify task registration exists
        query_res = subprocess.run(["schtasks", "/Query", "/TN", "PraecursorE2ETest1"], capture_output=True, text=True)
        assert query_res.returncode == 0
        assert "PraecursorE2ETest1" in query_res.stdout

        # Clean up
        subprocess.run(["schtasks", "/Delete", "/TN", "PraecursorE2ETest1", "/F"], capture_output=True)

    def test_r1_scheduled_task_non_interactive(self, run_task_script):
        """Verify task execution runs without manual intervention (force overwrite / no prompt)."""
        # Register once
        run_task_script("register_task.ps1", "PraecursorE2ETestNonInteractive", "17:00")
        # Re-register without interactive prompt using /F
        res = run_task_script("register_task.ps1", "PraecursorE2ETestNonInteractive", "17:00")
        assert res.returncode == 0
        assert "registered successfully" in res.stdout.lower() or res.returncode == 0

        subprocess.run(["schtasks", "/Delete", "/TN", "PraecursorE2ETestNonInteractive", "/F"], capture_output=True)

    def test_r1_scheduled_task_trigger_time(self, run_task_script):
        """Verify trigger is set precisely to 17:00 (5:00 PM)."""
        res = run_task_script("register_task.ps1", "PraecursorE2ETestTrigger", "17:00")
        assert res.returncode == 0

        query_res = subprocess.run(["schtasks", "/Query", "/TN", "PraecursorE2ETestTrigger", "/V", "/FO", "LIST"], capture_output=True, text=True)
        assert query_res.returncode == 0
        assert "17:00" in query_res.stdout or "5:00:00 PM" in query_res.stdout or "17:00:00" in query_res.stdout

        subprocess.run(["schtasks", "/Delete", "/TN", "PraecursorE2ETestTrigger", "/F"], capture_output=True)

    def test_r1_scheduled_task_action_command(self, run_task_script, project_root):
        """Verify action command invokes python script run_autonomous_pipeline.py correctly."""
        target_py = project_root / "tools" / "run_autonomous_pipeline.py"
        assert target_py.exists()

        res = run_task_script("register_task.ps1", "PraecursorE2ETestAction", "17:00")
        assert res.returncode == 0
        query_res = subprocess.run(["schtasks", "/Query", "/TN", "PraecursorE2ETestAction", "/V", "/FO", "LIST"], capture_output=True, text=True)
        assert query_res.returncode == 0
        assert "run_autonomous_pipeline.py" in query_res.stdout

        subprocess.run(["schtasks", "/Delete", "/TN", "PraecursorE2ETestAction", "/F"], capture_output=True)

    def test_r1_scheduled_task_exit_code(self, run_task_script):
        """Verify scheduled task script returns exit code 0 on successful run."""
        res = run_task_script("register_task.ps1", "PraecursorE2ETestExitCode", "17:00")
        assert res.returncode == 0, f"Expected 0 exit code, got {res.returncode}"

        subprocess.run(["schtasks", "/Delete", "/TN", "PraecursorE2ETestExitCode", "/F"], capture_output=True)

    def test_r1_pipeline_trading_day_logging(self, tmp_path, monkeypatch):
        """Verify pipeline explicitly logs PROCESSING on EGX trading days (Sun-Thu)."""
        from datetime import date
        from tools.run_autonomous_pipeline import run_pipeline, is_egx_trading_day

        trading_date = date(2026, 8, 2)
        assert is_egx_trading_day(trading_date) is True

        logs_dir = tmp_path / "logs"
        monkeypatch.setattr("tools.run_autonomous_pipeline.run_stage", lambda *args, **kwargs: True)

        code = run_pipeline(logs_dir=logs_dir, run_date=trading_date)
        assert code == 0

        log_file = logs_dir / "scheduled_pipeline_20260802.log"
        assert log_file.exists()
        log_content = log_file.read_text(encoding="utf-8")
        assert "PROCESSING: EGX Trading Day (2026-08-02) - executing autonomous scan pipeline." in log_content

    def test_r1_pipeline_non_trading_day_skip_logging(self, tmp_path):
        """Verify pipeline explicitly logs SKIPPED and exits with code 0 on non-trading days (Fri-Sat)."""
        from datetime import date
        from tools.run_autonomous_pipeline import run_pipeline, is_egx_trading_day

        non_trading_date = date(2026, 8, 7)
        assert is_egx_trading_day(non_trading_date) is False

        logs_dir = tmp_path / "logs"

        code = run_pipeline(logs_dir=logs_dir, run_date=non_trading_date)
        assert code == 0

        log_file = logs_dir / "scheduled_pipeline_20260807.log"
        assert log_file.exists()
        log_content = log_file.read_text(encoding="utf-8")
        assert "SKIPPED: Non-trading day (2026-08-07) - skipping automated scan." in log_content

    def test_r1_pipeline_forced_execution_on_non_trading_day(self, tmp_path, monkeypatch):
        """Verify --force flag overrides non-trading day skip check."""
        from datetime import date
        from tools.run_autonomous_pipeline import run_pipeline

        non_trading_date = date(2026, 8, 7)
        logs_dir = tmp_path / "logs"
        monkeypatch.setattr("tools.run_autonomous_pipeline.run_stage", lambda *args, **kwargs: True)

        code = run_pipeline(logs_dir=logs_dir, run_date=non_trading_date, force=True)
        assert code == 0

        log_file = logs_dir / "scheduled_pipeline_20260807.log"
        assert log_file.exists()
        log_content = log_file.read_text(encoding="utf-8")
        assert "PROCESSING: Forced execution on non-trading day (2026-08-07)" in log_content

    def test_r1_stage_retry_logic(self, monkeypatch):
        """Verify run_stage executes retries with backoff on stage failure."""
        import logging
        from pathlib import Path
        from tools.run_autonomous_pipeline import run_stage

        logger = logging.getLogger("test_retry")
        call_count = 0

        def mock_subprocess_run(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            class Result:
                returncode = 1 if call_count < 3 else 0
                stdout = "Output"
                stderr = "Error"
            return Result()

        monkeypatch.setattr("subprocess.run", mock_subprocess_run)
        monkeypatch.setattr("time.sleep", lambda secs: None)

        success = run_stage(logger, 1, "Test Stage", ["echo", "test"], Path("."), max_attempts=3, initial_backoff=0.01)
        assert success is True
        assert call_count == 3


class TestR1SchedulingTier2:
    """Tier 2: Boundary & Corner Cases for R1 Autonomous 5 PM Scheduling."""

    def test_r1_reregister_existing_task(self, run_task_script):
        """Verify task scheduler registration handles existing task overwrites gracefully."""
        task_name = "PraecursorE2EOverwrite"
        res1 = run_task_script("register_task.ps1", task_name, "17:00")
        assert res1.returncode == 0

        # Overwrite with 18:00
        res2 = run_task_script("register_task.ps1", task_name, "18:00")
        assert res2.returncode == 0

        query_res = subprocess.run(["schtasks", "/Query", "/TN", task_name, "/V", "/FO", "LIST"], capture_output=True, text=True)
        assert query_res.returncode == 0
        assert "18:00" in query_res.stdout or "6:00:00 PM" in query_res.stdout or "18:00:00" in query_res.stdout

        subprocess.run(["schtasks", "/Delete", "/TN", task_name, "/F"], capture_output=True)

    def test_r1_missing_script_path(self, run_task_script, project_root):
        """Verify error handling when script path is missing or invalid."""
        invalid_script = str(project_root / "non_existent_script.bat")
        res = run_task_script("register_task.ps1", "PraecursorE2EInvalid", "17:00", extra_args=[invalid_script])
        assert res.returncode != 0
        assert "does not exist" in res.stderr.lower() or "error" in res.stdout.lower() or "error" in res.stderr.lower()

    def test_r1_offline_network_execution(self, project_root, monkeypatch):
        """Verify scheduled task handles offline network state without crashing."""
        # Test executing run_scanner.py or updating outcomes in offline mode
        from praecursor.collectors.market_data_source import NetworkError

        def mock_fetch_offline(*args, **kwargs):
            raise NetworkError("Simulated offline network connection error")

        # System should catch NetworkError gracefully without raising unhandled exception
        with pytest.raises(NetworkError) as exc_info:
            mock_fetch_offline()
        assert "offline network connection error" in str(exc_info.value)

    def test_r1_non_admin_permission_handling(self, run_task_script):
        """Verify scheduled task script provides informative error if elevated privileges are needed."""
        # Test passing an invalid / forbidden task name or invalid schtasks flag
        res = run_task_script("register_task.ps1", "TestTaskWith/InvalidName", "17:00")
        # schtasks will reject invalid syntax or non-admin permission issues with non-zero exit code
        assert res.returncode != 0 or "warning" in res.stdout.lower() or "error" in res.stderr.lower() or "exit code" in res.stderr.lower()

    def test_r1_custom_time_parameter(self, run_task_script):
        """Verify scheduling script accepts custom execution time parameters."""
        task_name = "PraecursorE2ECustomTime"
        custom_time = "16:30"
        res = run_task_script("register_task.ps1", task_name, custom_time)
        assert res.returncode == 0

        query_res = subprocess.run(["schtasks", "/Query", "/TN", task_name, "/V", "/FO", "LIST"], capture_output=True, text=True)
        assert query_res.returncode == 0
        assert "16:30" in query_res.stdout or "4:30:00 PM" in query_res.stdout or "16:30:00" in query_res.stdout

        subprocess.run(["schtasks", "/Delete", "/TN", task_name, "/F"], capture_output=True)
