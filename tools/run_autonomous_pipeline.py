"""
Autonomous Headless Pipeline Runner for Praecursor-EGX.
Designed for unattended execution via Windows Task Scheduler.
Executes Scanner, Outcome Tracking, Retraining, Dashboard Generation, and Telegram Notifications.
"""

import argparse
from datetime import datetime, date
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = PROJECT_ROOT / "logs"


def update_scan_status(stage: float, stage_name: str, project_root: Path | None = None, **kwargs) -> None:
    """Helper function to atomically update data/scan_status.json."""
    root = project_root or PROJECT_ROOT
    data_dir = root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    status_file = data_dir / "scan_status.json"

    current_data = {
        "running": True,
        "stage": stage,
        "stage_name": stage_name,
        "processed": 0,
        "total": 0,
        "percent": 0.0,
        "current_symbol": None,
        "elapsed_seconds": 0,
        "eta_seconds": 0,
        "telegram_status": "Queued for Stage 4",
        "error": None,
        "completed": False,
    }

    if status_file.exists():
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
                if isinstance(existing, dict):
                    current_data.update(existing)
        except Exception:
            pass

    current_data["stage"] = stage
    current_data["stage_name"] = stage_name
    for k, v in kwargs.items():
        current_data[k] = v

    try:
        tmp_file = status_file.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(current_data, f, indent=2)
        os.replace(tmp_file, status_file)
    except Exception:
        pass


def is_egx_trading_day(target_date: date) -> bool:
    """Check if given date is an EGX trading day (Sunday=6, Monday=0, Tuesday=1, Wednesday=2, Thursday=3)."""
    return target_date.weekday() in (6, 0, 1, 2, 3)


def setup_logging(logs_dir: Path | None = None, run_date: date | None = None) -> tuple[logging.Logger, Path]:
    """Configure logging to stdout and file in logs/scheduled_pipeline_YYYYMMDD.log."""
    target_logs_dir = logs_dir or LOGS_DIR
    target_logs_dir.mkdir(parents=True, exist_ok=True)
    
    date_obj = run_date or datetime.now().date()
    today_str = date_obj.strftime("%Y%m%d")
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


def run_stage(
    logger: logging.Logger,
    stage_num: int | float,
    stage_name: str,
    cmd: list[str],
    cwd: Path,
    max_attempts: int = 3,
    initial_backoff: float = 10.0,
) -> bool:
    """Execute a single pipeline stage via subprocess with output logging and retry logic."""
    logger.info(f"=== [Stage {stage_num}] Starting: {stage_name} ===")
    logger.info(f"Command: {' '.join(cmd)}")
    
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            logger.info(f"=== [Stage {stage_num}] Retry attempt {attempt}/{max_attempts}: {stage_name} ===")
        try:
            res = subprocess.run(
                cmd,
                cwd=str(cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if res.stdout:
                for line in res.stdout.splitlines():
                    clean_line = line.rstrip()
                    if clean_line:
                        logger.info(clean_line)
            return_code = res.returncode

            if return_code == 0:
                logger.info(f"=== [Stage {stage_num}] Completed Successfully: {stage_name} ===")
                return True
            else:
                logger.error(
                    f"=== [Stage {stage_num}] Attempt {attempt}/{max_attempts} Failed: {stage_name} (Exit Code: {return_code}) ==="
                )
        except Exception as e:
            logger.error(f"=== [Stage {stage_num}] Unexpected exception in {stage_name} (Attempt {attempt}/{max_attempts}): {e} ===")
        
        if attempt < max_attempts:
            wait_time = initial_backoff * (2 ** (attempt - 1))
            logger.info(f"Waiting {wait_time:.1f} seconds before retrying {stage_name}...")
            time.sleep(wait_time)
            
    logger.error(f"=== [Stage {stage_num}] All {max_attempts} attempts failed for: {stage_name} ===")
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
    run_date: date | None = None,
    force: bool = False,
) -> int:
    """Execute the 5-stage autonomous daily pipeline."""
    root = project_root or PROJECT_ROOT
    effective_date = run_date or datetime.now().date()
    date_str = effective_date.strftime("%Y-%m-%d")
    
    from datetime import timedelta
    from zoneinfo import ZoneInfo
    now_cairo = datetime.now(ZoneInfo("Africa/Cairo"))
    if now_cairo.weekday() not in (4, 5) and now_cairo.hour < 10:
        next_trading_day = now_cairo.date()
    else:
        next_trading_day = effective_date + timedelta(days=1)
        while next_trading_day.weekday() in (4, 5):  # Friday, Saturday
            next_trading_day += timedelta(days=1)
    next_trading_day_str = next_trading_day.strftime("%Y-%m-%d")
    
    # Ensure reports output directories are prepared for next-day scan output files
    reports_dir = root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    archive_dir = reports_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    logger = None
    log_file = None
    try:
        logger, log_file = setup_logging(logs_dir, run_date=effective_date)
        

        os.environ["PRAECURSOR_PIPELINE_RUNNING"] = "1"
        logger.info("==================================================")
        logger.info("Praecursor-EGX Autonomous Daily Pipeline Started")
        logger.info(f"Project Root: {root}")
        logger.info(f"Log File: {log_file}")
        logger.info(f"Scan Date: {date_str}")
        logger.info(f"Target Date: {next_trading_day_str}")
        logger.info("==================================================")

        trading_day = is_egx_trading_day(effective_date)
        if not trading_day and not force:
            logger.info(f"SKIPPED: Non-trading day ({date_str}) - skipping automated scan.")
            return 0

        current_stage = 1.0
        current_stage_name = "Market Data & Symbol Scanner"
        completed_successfully = False
        pipeline_error = None

        # Start of Pipeline
        update_scan_status(
            stage=1,
            stage_name="Market Data & Symbol Scanner",
            running=True,
            completed=False,
            percent=0.0,
            telegram_status="Queued for Stage 4",
            error=None,
            project_root=root,
        )

        if trading_day:
            logger.info(f"PROCESSING: EGX Trading Day ({date_str}) - executing autonomous scan pipeline.")
        else:
            logger.info(f"PROCESSING: Forced execution on non-trading day ({date_str}) - executing autonomous scan pipeline.")

        python_exe = sys.executable
        stages_passed = 0
        total_stages = 5

        # Stage 1: Daily Scanner
        s1_cmd = [python_exe, "tools/run_scanner.py"]
        if run_date:
            s1_cmd.extend(["--date", date_str])
            
        s1_ok = run_stage(
            logger,
            1,
            "Daily Scanner",
            s1_cmd,
            root,
        )
        if not s1_ok:
            pipeline_error = "Stage 1 (Scanner) failed. Aborting downstream pipeline execution."
            logger.error(pipeline_error)
            return 1
        stages_passed += 1
            
        # Stage 1.5: Backfill Outcomes (uses freshly downloaded prices from Stage 1)
        current_stage = 1.5
        current_stage_name = "Outcome Backfill & Tracking"
        update_scan_status(
            stage=1.5,
            stage_name="Outcome Backfill & Tracking",
            percent=40.0,
            current_symbol=None,
            project_root=root,
        )
        outcome_cmd = [python_exe, "tools/track_outcomes.py"]
        s1_5_ok = run_stage(logger, 1.5, "Outcome Backfill", outcome_cmd, root)
        if s1_5_ok:
            stages_passed += 1
        else:
            logger.warning("Stage 1.5 (Outcome Backfill) completed with errors.")

        # Stage 2: Model Retraining
        current_stage = 2.0
        current_stage_name = "XGBoost & LightGBM Model Retraining"
        update_scan_status(
            stage=2,
            stage_name="XGBoost & LightGBM Model Retraining",
            percent=60.0,
            current_symbol=None,
            project_root=root,
        )
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
        current_stage = 3.0
        current_stage_name = "Institutional Dashboard Generation"
        update_scan_status(
            stage=3,
            stage_name="Institutional Dashboard Generation",
            percent=80.0,
            current_symbol=None,
            project_root=root,
        )
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

        # Stage 4: Notifications Broadcast (Telegram)
        current_stage = 4.0
        current_stage_name = "Telegram Summary Broadcast"
        update_scan_status(
            stage=4,
            stage_name="Telegram Summary Broadcast",
            percent=95.0,
            telegram_status="Delivering...",
            current_symbol=None,
            project_root=root,
        )
        from praecursor.notifications.telegram import TelegramSettings
        tg_settings = TelegramSettings.load()
        has_telegram_credentials = tg_settings.is_configured
        
        telegram_cmd = [python_exe, "tools/send_telegram_report.py", "--use-latest"]
        if dry_run_telegram or not has_telegram_credentials:
            if not has_telegram_credentials:
                logger.info("Telegram credentials not configured in config/telegram.json. Operating in --dry-run mode.")
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

        overall_success = s1_ok and s2_ok and s3_ok
        if overall_success:
            completed_successfully = True
            update_scan_status(
                stage=5,
                stage_name="Complete",
                running=False,
                completed=True,
                percent=100.0,
                telegram_status="Delivered ✅",
                eta_seconds=0,
                current_symbol=None,
                project_root=root,
            )
            logger.info(f"Pipeline completed successfully. ({stages_passed}/{total_stages} stages passed)")
            return 0
        else:
            pipeline_error = f"Pipeline finished with warnings/errors. ({stages_passed}/{total_stages} stages passed)"
            logger.error(pipeline_error)
            return 1
    except Exception as err:
        pipeline_error = str(err)
        if logger:
            logger.error(f"Pipeline failed with exception: {err}")
        return 1
    finally:
        os.environ.pop("PRAECURSOR_PIPELINE_RUNNING", None)
        if not completed_successfully and current_stage > 0:
            err_msg = pipeline_error or "Pipeline terminated"
            update_scan_status(
                stage=current_stage,
                stage_name=current_stage_name,
                running=False,
                error=err_msg,
                project_root=root,
            )
        if logger:
            close_logging(logger)


def main() -> int:
    parser = argparse.ArgumentParser(description="Autonomous Pipeline Runner for Praecursor-EGX.")
    parser.add_argument(
        "--dry-run-telegram",
        action="store_true",
        help="Force --dry-run for Telegram broadcast stage.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force pipeline execution even on non-trading days.",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Target date in YYYY-MM-DD format (for backtesting / manual triggers).",
    )
    args = parser.parse_args()

    parsed_date = None
    if args.date:
        try:
            parsed_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"Error: Invalid date format '{args.date}'. Expected YYYY-MM-DD.", file=sys.stderr)
            return 1

    return run_pipeline(
        dry_run_telegram=args.dry_run_telegram,
        run_date=parsed_date,
        force=args.force,
    )


if __name__ == "__main__":
    sys.exit(main())
