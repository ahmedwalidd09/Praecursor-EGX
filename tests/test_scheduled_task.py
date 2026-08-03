"""
Tests for Praecursor-EGX Autonomous 5 PM Task Scheduler Integration & Automation.
"""

from datetime import datetime
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_ROOT / "tools"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(TOOLS_DIR))

from run_autonomous_pipeline import run_pipeline, run_stage, setup_logging


class TestScheduledTaskArtifacts(unittest.TestCase):
    """Verify that all required scheduler automation scripts exist and contain correct parameters."""

    def test_required_script_files_exist(self):
        required_files = [
            TOOLS_DIR / "run_autonomous_pipeline.py",
            TOOLS_DIR / "register_scheduled_task.ps1",
            TOOLS_DIR / "register_scheduled_task.bat",
            TOOLS_DIR / "unregister_scheduled_task.ps1",
        ]
        for script_path in required_files:
            self.assertTrue(script_path.exists(), f"Missing required automation script: {script_path}")

    def test_powershell_installer_parameters(self):
        ps1_path = TOOLS_DIR / "register_scheduled_task.ps1"
        content = ps1_path.read_text(encoding="utf-8")

        # Task Name
        self.assertIn('TaskName = "Praecursor-EGX Daily Scanner"', content)
        
        # Schedule (5:00 PM / 17:00)
        self.assertIn('Time = "17:00"', content)

        # Days of Week (Sunday - Thursday)
        for day in ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"]:
            self.assertIn(day, content)

        # Settings
        self.assertIn("-AllowStartIfOnBatteries", content)
        self.assertIn("-DontStopIfGoingOnBatteries", content)
        self.assertIn("-StartWhenAvailable", content)
        self.assertIn("-ExecutionTimeLimit", content)
        self.assertIn("-RestartCount", content)

        # Runner Script Reference
        self.assertIn("run_autonomous_pipeline.py", content)

    def test_batch_wrapper_content(self):
        bat_path = TOOLS_DIR / "register_scheduled_task.bat"
        content = bat_path.read_text(encoding="utf-8")

        self.assertIn("powershell", content.lower())
        self.assertIn("-executionpolicy bypass", content.lower())
        self.assertIn("register_scheduled_task.ps1", content)
        self.assertIn("exit /b", content)

    def test_uninstaller_script_content(self):
        ps1_path = TOOLS_DIR / "unregister_scheduled_task.ps1"
        content = ps1_path.read_text(encoding="utf-8")

        self.assertIn('TaskName = "Praecursor-EGX Daily Scanner"', content)
        self.assertIn("Unregister-ScheduledTask", content)


class TestHeadlessPipelineRunner(unittest.TestCase):
    """Verify logging, stage execution, and exit code propagation of the autonomous pipeline."""

    def test_logging_setup_creates_log_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_logs_dir = Path(tmp_dir) / "logs"
            logger, log_file = setup_logging(tmp_logs_dir)
            try:
                logger.info("Test log entry")

                today_str = datetime.now().strftime("%Y%m%d")
                expected_filename = f"scheduled_pipeline_{today_str}.log"
                self.assertEqual(log_file.name, expected_filename)
                self.assertTrue(log_file.exists())
                
                content = log_file.read_text(encoding="utf-8")
                self.assertIn("Test log entry", content)
            finally:
                from run_autonomous_pipeline import close_logging
                close_logging(logger)

    def test_run_stage_success_and_failure(self):
        logger = MagicMock()
        with tempfile.TemporaryDirectory() as tmp_dir:
            cwd = Path(tmp_dir)
            
            # Successful command
            success = run_stage(logger, 1, "Success Stage", [sys.executable, "-c", "print('OK')"], cwd)
            self.assertTrue(success)

            # Failing command
            failure = run_stage(logger, 2, "Failure Stage", [sys.executable, "-c", "import sys; sys.exit(42)"], cwd)
            self.assertFalse(failure)

    @patch("run_autonomous_pipeline.run_stage")
    def test_run_pipeline_success_exit_code(self, mock_run_stage):
        mock_run_stage.side_effect = [True, True, True, True]
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code = run_pipeline(project_root=Path(tmp_dir), logs_dir=Path(tmp_dir) / "logs")
            self.assertEqual(exit_code, 0)
            self.assertEqual(mock_run_stage.call_count, 4)

    @patch("run_autonomous_pipeline.run_stage")
    def test_run_pipeline_stage1_failure_aborts(self, mock_run_stage):
        mock_run_stage.side_effect = [False]
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code = run_pipeline(project_root=Path(tmp_dir), logs_dir=Path(tmp_dir) / "logs")
            self.assertEqual(exit_code, 1)
            self.assertEqual(mock_run_stage.call_count, 1)

    @patch("run_autonomous_pipeline.run_stage")
    def test_run_pipeline_stage2_failure_propagates(self, mock_run_stage):
        mock_run_stage.side_effect = [True, False, True, True]
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code = run_pipeline(project_root=Path(tmp_dir), logs_dir=Path(tmp_dir) / "logs")
            self.assertEqual(exit_code, 1)
            self.assertEqual(mock_run_stage.call_count, 4)


if __name__ == "__main__":
    unittest.main()
