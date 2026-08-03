"""
Autonomous Headless Pipeline Runner for Praecursor-EGX.
Designed for unattended execution via Windows Task Scheduler.
Executes Scanner, Outcome Tracking, Retraining, Dashboard Generation, and Telegram Notifications.
"""

import argparse
from datetime import datetime
import logging
import os
from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = PROJECT_ROOT / "logs"


def setup_logging(logs_dir: Path | None = None) -> tuple[logging.Logger, Path]:
    """Configure logging to stdout and file in logs/scheduled_pipeline_YYYYMMDD.log."""
    target_logs_dir = logs_dir or LOGS_DIR
    target_logs_dir.mkdir(parents=True, exist_ok=True)
    
    today_str = datetime.now().strftime("%Y%m%d")
    log_file = target_logs_dir / f"scheduled_pipeline_{today_str}.log"

    logger = logging.getLogger("praecursor.autonomous_pipeline")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger, log_file


def run_stage(logger: logging.Logger, stage_num: int, stage_name: str, cmd: list[str], cwd: Path) -> bool:
    """Execute a single pipeline stage via subprocess and log output."""
    logger.info(f"=== [Stage {stage_num}/4] Starting: {stage_name} ===")
    logger.info(f"Command: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout and result.stdout.strip():
            logger.info(f"[{stage_name} Output]\n{result.stdout.strip()}")
        
        if result.returncode == 0:
            logger.info(f"=== [Stage {stage_num}/4] Completed Successfully: {stage_name} ===")
            return True
        else:
            logger.error(
                f"=== [Stage {stage_num}/4] Failed: {stage_name} (Exit Code: {result.returncode}) ==="
            )
            if result.stderr and result.stderr.strip():
                logger.error(f"[{stage_name} Error Output]\n{result.stderr.strip()}")
            return False
    except Exception as e:
        logger.error(f"=== [Stage {stage_num}/4] Unexpected exception in {stage_name}: {e} ===")
        return False


def close_logging(logger: logging.Logger):
    """Close and detach all handlers from logger to release file locks."""
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)


def run_pipeline(
    project_root: Path | None = None,
    logs_dir: Path | None = None,
    dry_run_telegram: bool = False,
) -> int:
    """Execute the 4-stage autonomous daily pipeline."""
    root = project_root or PROJECT_ROOT
    logger, log_file = setup_logging(logs_dir)
    
    try:
        logger.info("==================================================")
        logger.info("Praecursor-EGX Autonomous Daily Pipeline Started")
        logger.info(f"Project Root: {root}")
        logger.info(f"Log File: {log_file}")
        logger.info("==================================================")

        python_exe = sys.executable
        stages_passed = 0
        total_stages = 4

        # Stage 1: Daily Scanner & Outcome Tracking
        s1_ok = run_stage(
            logger,
            1,
            "Daily Scanner & Outcome Tracking",
            [python_exe, "tools/run_scanner.py"],
            root,
        )
        if not s1_ok:
            logger.error("Stage 1 (Scanner) failed. Aborting downstream pipeline execution.")
            return 1
        stages_passed += 1

        # Stage 2: Model Retraining
        s2_ok = run_stage(
            logger,
            2,
            "Model Retraining",
            [python_exe, "tools/retrain_models.py"],
            root,
        )
        if s2_ok:
            stages_passed += 1
        else:
            logger.warning("Stage 2 (Model Retraining) completed with errors.")

        # Stage 3: Dashboard Regeneration
        s3_ok = run_stage(
            logger,
            3,
            "Dashboard Regeneration",
            [python_exe, "tools/regenerate_dashboard.py"],
            root,
        )
        if s3_ok:
            stages_passed += 1
        else:
            logger.warning("Stage 3 (Dashboard Regeneration) completed with errors.")

        # Stage 4: Telegram Summary Broadcast
        has_telegram_credentials = bool(
            os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID")
        )
        
        telegram_cmd = [python_exe, "tools/send_telegram_report.py", "--use-latest"]
        if dry_run_telegram or not has_telegram_credentials:
            if not has_telegram_credentials:
                logger.info("Telegram credentials not found in environment. Operating in --dry-run mode.")
            telegram_cmd.append("--dry-run")

        s4_ok = run_stage(
            logger,
            4,
            "Telegram Summary Broadcast",
            telegram_cmd,
            root,
        )
        if s4_ok:
            stages_passed += 1
        else:
            logger.warning("Stage 4 (Telegram Broadcast) completed with errors.")

        overall_success = s1_ok and s2_ok and s3_ok and s4_ok
        if overall_success:
            logger.info(f"Pipeline completed successfully. ({stages_passed}/{total_stages} stages passed)")
            return 0
        else:
            logger.error(f"Pipeline finished with warnings/errors. ({stages_passed}/{total_stages} stages passed)")
            return 1
    finally:
        close_logging(logger)


def main() -> int:
    parser = argparse.ArgumentParser(description="Autonomous Pipeline Runner for Praecursor-EGX.")
    parser.add_argument(
        "--dry-run-telegram",
        action="store_true",
        help="Force --dry-run for Telegram broadcast stage.",
    )
    args = parser.parse_args()
    return run_pipeline(dry_run_telegram=args.dry_run_telegram)


if __name__ == "__main__":
    sys.exit(main())
