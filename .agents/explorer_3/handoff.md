# Handoff Report — Explorer 3: Pipeline Execution & Windows Task Scheduler Automation

## 1. Observation

### Existing Entry Points Analysis
1. **`main.py` & `PRAECURSOR.py`**:
   - Both files are identical 37-line toy demonstration scripts.
   - They load raw CSV data from `data/raw/sample.csv`, calculate EMA(20) and RSI(14) using legacy loader objects, and print raw results to standard output.
   - They **do not** invoke the real EGX production scanner, multi-source consensus engine, SQLite price cache, accuracy tracker, report archiving, XGBoost predictions, or Telegram notifications.

2. **`Daily Praecursor Update.bat`**:
   - Location: Project root (`C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\Daily Praecursor Update.bat`).
   - File Content (Verbatim line analysis):
     - Line 6: `cd /d "%USERPROFILE%\.gemini\antigravity\scratch\Praecursor-EGX"` (Hardcoded user path reliance).
     - Line 9: `start "Praecursor Dashboard Server" cmd /k "title Praecursor Dashboard Server && echo Leave this window open... && python -m praecursor.cli.dashboard"` (Launches an interactive GUI shell window to run the dashboard server).
     - Line 13: `python tools/run_scanner.py` (Runs scanner CLI wrapper).
     - Line 17: `start http://127.0.0.1:8000` (Launches default web browser via Windows shell GUI).
     - Line 21: `pause` (Waits for interactive keyboard input).
   - **Operational Blockers for Unattended Scheduling**:
     - `pause` forces the command prompt process to hang indefinitely when executed non-interactively via Windows Task Scheduler.
     - `start http://...` attempts to launch a GUI browser window, which fails or hangs when executed under non-interactive Task Scheduler sessions (Session 0).
     - `start "..." cmd /k` spawns an interactive child CMD process that never terminates.
     - Lacks file-based logging, error reporting, exit code propagation, and environment isolation.

3. **CLI Entry Points (`pyproject.toml`)**:
   - `praecursor-scan` = `praecursor.cli.scanner:main`
   - `praecursor-history` = `praecursor.cli.history:main`
   - `praecursor-sources` = `praecursor.cli.sources:main`
   - `praecursor-reports` = `praecursor.cli.reports:main`
   - `praecursor-backtest` = `praecursor.cli.backtest:main`
   - `praecursor-telegram` = `praecursor.cli.telegram:main`
   - `praecursor-dashboard` = `praecursor.cli.dashboard:main`

4. **Python Automation Scripts (`tools/`)**:
   - `tools/run_scanner.py`: Invokes `praecursor.cli.scanner.main()`, followed by `AccuracyTracker().update_historical_outcomes()`.
   - `tools/retrain_models.py`: Retrains XGBoost model using historical outcomes from `database/praecursor.db` and updates `models/xgboost_next_day.json`.
   - `tools/send_telegram_report.py`: Invokes `praecursor.cli.telegram:main` to broadcast market candidate summaries.
   - `tools/regenerate_dashboard.py`: Regenerates `reports/dashboard.html` directly from database history.

---

## 2. Logic Chain

### Execution Flow Tracing (Daily Update & Scan Pipeline)
When an end-to-end daily update and scan cycle executes, the step-by-step logic chain is:

1. **Invocation**:
   `tools/run_scanner.py` is invoked with Python runtime.

2. **Configuration & Symbol Resolution**:
   - `praecursor.cli.scanner.parse_args()` reads settings from `config/scanner.json` (defaults: `lookback_days` = 450, `consensus_lookback_days` = 180, `minimum_bars` = 10, `enable_consensus` = True, `enable_history` = True, `enable_archive_reports` = True).
   - Symbol universe is resolved from `config/symbols.csv` via `SymbolMapper`.

3. **Data Fetching & Consensus Verification**:
   - `ScannerWorkflow.run()` iterates through each symbol in the universe.
   - Primary OHLCV data is downloaded via `TradingViewSource`.
   - Secondary prices are downloaded via `StockAnalysisSource` and `MubasherSource`.
   - `PriceConsensusEngine.calculate()` evaluates the latest trade date prices across sources (0.5% price tolerance, minimum 2 agreeing sources).
   - If primary data contains discrepancies (>0.5% deviation) but consensus agrees, `PriceCache.override_close()` corrects the cached entry in `database/praecursor.db`.

4. **Feature Extraction & Technical Scoring**:
   - `CachedStockBuilder` constructs historical `Stock` instances from `database/praecursor.db`.
   - `OpportunityScorer` evaluates 20 technical indicators (EMA, RSI, MACD, ATR, Turnover, LimitUp, EGX30 Market Regime HMM).
   - XGBoost machine learning model (`models/xgboost_next_day.json`) generates breakout probability scores.
   - `NextDayPrediction` and `SwingPrediction` models score and classify candidates.

5. **Report Archiving & Output Generation**:
   - Output CSV reports generated: `reports/opportunity_ranking.csv`, `reports/next_day_candidates.csv`, `reports/swing_candidates.csv`.
   - Output Markdown report generated: `reports/opportunity_ranking.md`.
   - Timestamped historical archive reports saved to `reports/archive/opportunity_ranking_YYYYMMDD_HHMMSS.csv` and `.md`.
   - Interactive HTML dashboard generated: `reports/dashboard.html`.

6. **Signal History & Historical Outcome Tracking**:
   - Run metadata and candidate signals saved to `scanner_runs` and `scanner_signals` tables in `database/praecursor.db`.
   - `AccuracyTracker.update_historical_outcomes()` evaluates past signals against actual subsequent market prices (evaluating intraday high target hit `high >= entry * (1 + target_pct)` or gains `>= 2.5%`) and updates `scanner_signal_outcomes`.

7. **Continuous Learning Retraining & Notifications** (Required Automation Pipeline Extensions):
   - Continuous model retraining (`tools/retrain_models.py`) updates the XGBoost weights based on newly verified outcomes.
   - Telegram notifier (`tools/send_telegram_report.py`) sends automated daily candidate alerts.

---

## 3. Caveats

1. **Non-Interactive Windows Task Scheduler Execution (Session 0)**:
   - Tasks running under Windows Task Scheduler often execute in background Session 0. Any batch file or script containing interactive elements (`pause`, `cmd /k`, `start http://`) will block permanently or fail silently.
2. **EGX Trading Schedule vs. Standard Workdays**:
   - Egyptian Exchange (EGX) trading days run **Sunday through Thursday** (Sunday=Day 0, Thursday=Day 4).
   - Friday and Saturday are non-trading weekend days.
   - Market session closes at 2:30 PM EET/EEST. 5:00 PM (17:00) is the optimal scheduled run time as data providers (TradingView, Mubasher, StockAnalysis) complete post-close settling.
3. **Execution Policy & Elevation**:
   - Running PowerShell registration scripts requires `-ExecutionPolicy Bypass`.
   - Registering a scheduled task with `-RunLevel Highest` or system permissions requires Administrative privileges. Registering under the active logged-on user account works with standard user privileges when configured for "Run only when user is logged on".
4. **Environment Context**:
   - Python path must be dynamically resolved (`where python` or `sys.executable`) to avoid dependency issues when run outside an activated virtual environment.

---

## 4. Conclusion & Recommendations

### Requirement R1 Architecture Recommendation
To fulfill requirement R1 (Autonomous 5 PM Scheduling & Pipeline Automation), we recommend creating three modular automation scripts in `tools/`:

1. **`tools/run_autonomous_pipeline.py`** (Headless Autonomous Runner):
   - Executes the complete 4-stage pipeline non-interactively:
     - Stage 1: Daily Scanner & Historical Outcome Tracker (`tools/run_scanner.py`).
     - Stage 2: Continuous Model Retraining (`tools/retrain_models.py`).
     - Stage 3: Dashboard Regeneration (`tools/regenerate_dashboard.py`).
     - Stage 4: Telegram Summary Broadcast (`tools/send_telegram_report.py`).
   - Handles file-based logging (`logs/scheduled_pipeline_YYYYMMDD.log`).
   - Propagates exit codes (0 on success, non-zero on failure) without interactive pauses or GUI popups.

2. **`tools/register_scheduled_task.ps1`** (PowerShell Task Scheduler Installer):
   - Registers a Windows Scheduled Task named `Praecursor-EGX Daily Scanner`.
   - Schedule: Weekly on **Sunday, Monday, Tuesday, Wednesday, Thursday** at **17:00 (5:00 PM)**.
   - Configures settings: Wake to run (if supported), allow start on battery, restart on failure, execution time limit (30 mins).
   - Action: Launches `python.exe` executing `tools/run_autonomous_pipeline.py` with working directory set to project root.

3. **`tools/register_scheduled_task.bat`** (1-Click Batch Wrapper):
   - Simple Batch script executing `register_scheduled_task.ps1` via `powershell.exe -ExecutionPolicy Bypass`.

4. **`tools/unregister_scheduled_task.ps1`** (PowerShell Task Uninstaller):
   - Easily removes the scheduled task when needed.

---

### Concrete Script Specifications & Designs

#### Script 1: `tools/run_autonomous_pipeline.py`
```python
"""
Autonomous Headless Pipeline Runner for Praecursor-EGX.
Designed for unattended execution via Windows Task Scheduler.
Executes Scanner, Outcome Tracking, Retraining, Dashboard Generation, and Telegram Notifications.
"""

import sys
import os
import subprocess
import logging
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = PROJECT_ROOT / "logs"

def setup_logging():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"scheduled_pipeline_{datetime.now().strftime('%Y%m%d')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return log_file

def run_step(description: str, cmd: list[str]) -> bool:
    logging.info(f"=== Starting: {description} ===")
    try:
        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            check=True
        )
        if result.stdout:
            logging.info(f"Output:\n{result.stdout.strip()}")
        logging.info(f"=== Completed Successfully: {description} ===")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"=== Failed: {description} (Exit Code: {e.returncode}) ===")
        if e.stdout:
            logging.error(f"Stdout:\n{e.stdout.strip()}")
        if e.stderr:
            logging.error(f"Stderr:\n{e.stderr.strip()}")
        return False
    except Exception as e:
        logging.error(f"=== Unexpected Error during {description}: {e} ===")
        return False

def main() -> int:
    log_file = setup_logging()
    logging.info(f"Praecursor-EGX Autonomous Pipeline Started. Log File: {log_file}")
    
    python_exe = sys.executable

    # 1. Run Scanner & Accuracy Tracker
    ok = run_step("Daily Scanner & Outcome Update", [python_exe, "tools/run_scanner.py"])
    if not ok:
        logging.error("Scanner stage failed. Aborting pipeline.")
        return 1

    # 2. Retrain ML Models
    run_step("XGBoost Model Retraining", [python_exe, "tools/retrain_models.py"])

    # 3. Regenerate Dashboard
    run_step("Dashboard Regeneration", [python_exe, "tools/regenerate_dashboard.py"])

    # 4. Send Telegram Alerts (if configured)
    run_step("Telegram Notifications", [python_exe, "tools/send_telegram_report.py", "--run-scanner", "--dry-run"])

    logging.info("Praecursor-EGX Autonomous Pipeline Completed Successfully.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

#### Script 2: `tools/register_scheduled_task.ps1`
```powershell
<#
.SYNOPSIS
    Registers Praecursor-EGX Daily Update in Windows Task Scheduler for 5:00 PM on EGX Trading Days (Sun-Thu).
#>

[CmdletBinding()]
param (
    [string]$TaskName = "Praecursor-EGX Daily Scanner",
    [string]$Time = "17:00",
    [string]$ProjectPath = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectPath)) {
    $ProjectPath = Resolve-Path (Join-Path $PSScriptRoot "..")
}

$PythonPath = (Get-Command python).Source
if (-not $PythonPath) {
    Write-Error "Python executable not found in PATH."
    exit 1
}

$ScriptPath = Join-Path $ProjectPath "tools\run_autonomous_pipeline.py"
if (-not (Test-Path $ScriptPath)) {
    Write-Error "Runner script not found at $ScriptPath"
    exit 1
}

Write-Host "Registering Scheduled Task '$TaskName'..."
Write-Host "Project Directory: $ProjectPath"
Write-Host "Python Executable: $PythonPath"
Write-Host "Trigger Days: Sunday, Monday, Tuesday, Wednesday, Thursday at $Time"

# Create Action
$Action = New-ScheduledTaskAction `
    -Execute $PythonPath `
    -Argument "`"$ScriptPath`"" `
    -WorkingDirectory $ProjectPath

# Create Triggers (Sunday to Thursday at 5:00 PM)
$Trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -DaysOfWeek Sunday, Monday, Tuesday, Wednesday, Thursday `
    -At $Time

# Create Settings
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

# Register Task
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Automated daily EGX stock scan, outcome tracking, retraining, and reporting for Praecursor-EGX at 5:00 PM on trading days." `
    -Force

Write-Host "Task '$TaskName' registered successfully!" -ForegroundColor Green
```

#### Script 3: `tools/register_scheduled_task.bat`
```cmd
@echo off
echo ===================================================
echo PRAECURSOR-EGX TASK SCHEDULER REGISTRATION
echo ===================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0register_scheduled_task.ps1"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Task registration completed successfully!
) else (
    echo.
    echo ERROR: Task registration failed with exit code %ERRORLEVEL%.
)
echo.
pause
```

---

## 5. Verification Method

To independently verify the Task Scheduler automation and pipeline flow:

1. **Verify Script Invocations Non-Interactively**:
   Execute the autonomous pipeline script manually via PowerShell:
   ```powershell
   python tools/run_autonomous_pipeline.py
   ```
   Check `logs/scheduled_pipeline_YYYYMMDD.log` to verify that all 4 stages (Scanner, Retraining, Dashboard, Telegram) execute cleanly without prompts.

2. **Verify Task Scheduler Registration**:
   Execute registration script:
   ```powershell
   powershell -ExecutionPolicy Bypass -File tools/register_scheduled_task.ps1
   ```
   Query Task Scheduler status:
   ```powershell
   Get-ScheduledTask -TaskName "Praecursor-EGX Daily Scanner"
   ```
   Confirm Trigger is set to `Weekly` for `Sunday, Monday, Tuesday, Wednesday, Thursday` at `17:00`.

3. **Verify Unattended Trigger Execution**:
   Run the scheduled task immediately on-demand to verify exit code and log generation:
   ```powershell
   Start-ScheduledTask -TaskName "Praecursor-EGX Daily Scanner"
   Get-ScheduledTaskInfo -TaskName "Praecursor-EGX Daily Scanner"
   ```
   Inspect `LastTaskResult` (must be `0`) and check generated logs in `logs/`.
