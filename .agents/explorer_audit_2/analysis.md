# Requirement R2 Audit & Analysis Report: Autonomous 5 PM Automation Pipeline & Task Scheduler Integration

## Executive Summary
This audit evaluates Requirement R2 (**Bulletproof 5 PM Automation Pipeline & Task Scheduler Integration**) for Praecursor-EGX. The scope encompasses the execution entry point (`tools/run_autonomous_pipeline.py`), Task Scheduler registration scripts (`register_task.ps1`, `tools/register_scheduled_task.ps1`, batch files), error recovery, weekend/holiday logic, next-day scan prep, and manual execution triggers.

Key findings include:
1. **Script Discrepancy & Task Scheduler Confusion**: Multiple conflicting registration scripts exist. The primary root script (`register_task.ps1`) and `tools/register_task.ps1` point to `Daily Praecursor Update.bat` which is **interactive** (`pause` command, opening browser windows) and only executes `tools/run_scanner.py`, bypassing stages 2–4. In contrast, `tools/register_scheduled_task.ps1` correctly targets `tools/run_autonomous_pipeline.py` with EGX trading days (Sun–Thu).
2. **Lack of Internal Network Retry Logic**: `tools/run_autonomous_pipeline.py` executes pipeline stages via `subprocess.run` with single-attempt execution (`check=False`). If a transient network glitch occurs during Stage 1 (Scanner), the pipeline aborts immediately without attempting in-process retries or backoff.
3. **Missing Weekend & Holiday Explicit Logging**: `tools/run_autonomous_pipeline.py` lacks trading day validation logic. If executed on a Friday or Saturday (or market holiday), it blindly runs the scanner without logging whether the day was skipped or processed as an EGX trading day.
4. **Interactive Batch Blocking**: `Daily Praecursor Update.bat` contains a `pause` statement and interactive GUI actions (`start http://127.0.0.1:8000`), which hang headless Task Scheduler executions in Session 0.

---

## 1. Audit of Task Scheduler Registration & Integration Scripts

### 1.1 File Inventory & Script Analysis

| Script Path | Execution Target | Schedule / Trigger | Interactive / Headless | Assessment & Gaps |
|-------------|------------------|--------------------|------------------------|-------------------|
| `register_task.ps1` (Root) | `Daily Praecursor Update.bat` | `DAILY` @ 17:00 | **Interactive (Hangs)** | ❌ **CRITICAL BUG**: Points to `.bat` containing `pause`. Uses `/SC DAILY` (7 days) instead of EGX trading days (Sun–Thu). |
| `tools/register_task.ps1` | `Daily Praecursor Update.bat` | `DAILY` @ 17:00 | **Interactive (Hangs)** | ❌ **CRITICAL BUG**: Identical issue as root script. Overwrites Task Scheduler with legacy interactive script. |
| `tools/register_scheduled_task.ps1` | `tools/run_autonomous_pipeline.py` | `Sun,Mon,Tue,Wed,Thu` @ 17:00 | **Headless** | ✅ **CORRECT DESIGN**: Uses `New-ScheduledTaskTrigger` for EGX trading days, sets 3x retry on failure (5m interval), 30m limit. |
| `tools/register_task.bat` | `Daily Praecursor Update.bat` | `DAILY` @ 17:00 | **Interactive (Hangs)** | ❌ Legacy wrapper for `tools/register_task.ps1`. |
| `tools/register_scheduled_task.bat` | `tools/register_scheduled_task.ps1` | Delegate to PS1 | **Headless** | ✅ Correct batch entry point for scheduling. |
| `Daily Praecursor Update.bat` | `python tools/run_scanner.py` | N/A (Manual runner) | **Interactive** | ❌ Contains `pause`, `start http://...`, starts dashboard server in new cmd window. Unsuitable for Task Scheduler. |
| `tools/unregister_scheduled_task.ps1` | schtasks /Delete | N/A | Headless | ✅ Clean removal utility for scheduled task. |

### 1.2 Identified Architectural Discrepancies
- **Duplicate Registration Entry Points**: `register_task.ps1` in the project root is tested by `tests/e2e/test_r1_scheduling.py`. However, `register_task.ps1` points to `Daily Praecursor Update.bat` instead of `tools/run_autonomous_pipeline.py`!
- **Interactive Command Blocking**: When Task Scheduler executes a batch script containing `pause`, the command prompt waits indefinitely for keystrokes in a hidden background session (Session 0), consuming memory and causing future scheduled runs to fail or overlap.

---

## 2. Audit of Pipeline Execution Flow & Stage Management

`tools/run_autonomous_pipeline.py` orchestrates execution across 4 distinct stages:

```
[Stage 1/4] Daily Scanner & Outcome Tracking (tools/run_scanner.py)
      │
      ├──> If Success (Exit 0): Proceed to Stage 2
      └──> If Failure (Exit 1): Abort Downstream Pipeline immediately (return 1)
      │
[Stage 2/4] Model Retraining (tools/retrain_models.py)
      │
[Stage 3/4] Dashboard Regeneration (tools/regenerate_dashboard.py)
      │
[Stage 4/4] Telegram Summary Broadcast (tools/send_telegram_report.py)
```

### 2.1 Stage Failure Policies
- **Stage 1 (Scanner)** is critical: If Stage 1 fails, stages 2–4 are skipped, and `run_pipeline()` returns exit code `1`.
- **Stages 2, 3, and 4** are non-fatal: If Stage 2 or 3 or 4 fails, a warning is logged, but remaining downstream stages continue. The final pipeline exit code is `1` if any stage had errors.

---

## 3. Audit of Network Error Recovery and Retry Logic

### 3.1 Subprocess & Execution Level Analysis
- `run_stage()` uses `subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)`.
- If an HTTP request timeout or network socket disconnect occurs in `tools/run_scanner.py` (e.g., when querying TradingView or Mubasher), `subprocess.run` returns exit code 1 immediately.
- `run_autonomous_pipeline.py` has **no internal retry loop** (e.g., retrying Stage 1 up to 3 times with exponential backoff before marking it as failed).

### 3.2 Task Scheduler Failure Retry Policy
- `tools/register_scheduled_task.ps1` configures Windows Task Scheduler restart policies:
  `-RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5)`
- This relies on Task Scheduler restarting the whole Python process 5 minutes later if Python exits with non-zero code.
- **Gap**: If the script is run manually from CLI (`python tools/run_autonomous_pipeline.py`) or triggered via legacy batch scripts, Task Scheduler restart policies do NOT apply.

---

## 4. Audit of Weekend & Holiday Handling

### 4.1 EGX Trading Schedule Context
- EGX (Egyptian Exchange) trading days are **Sunday, Monday, Tuesday, Wednesday, Thursday**.
- Friday and Saturday are weekend days.
- Public holidays (e.g., Eid, Revolution Day, New Year) are non-trading days.

### 4.2 Code Audit Findings
1. **`tools/run_autonomous_pipeline.py`**:
   - Has **zero** day-of-week checks (`datetime.now().weekday()`).
   - Has **no** explicit log messages stating: `SKIPPED: Today is a weekend/holiday (Friday/Saturday)` or `PROCESSING: EGX Trading Day (Sunday)`.
2. **`register_task.ps1` (root)**:
   - Uses `/SC DAILY` which schedules task execution 7 days a week, causing unnecessary execution on Fridays and Saturdays.
3. **`tools/register_scheduled_task.ps1`**:
   - Correctly specifies `-DaysOfWeek Sunday, Monday, Tuesday, Wednesday, Thursday`. However, Task Scheduler trigger filtering alone does not fulfill the requirement for explicit Python log output when running on non-trading days.

---

## 5. Audit of Next-Day Scan Preparation Logic

### 5.1 Artifact & Data Generation Workflow
When `tools/run_scanner.py` executes during Stage 1:
1. `ScannerWorkflow.run()` fetches OHLCV data up to `end_date` (today).
2. Computes technical indicators, opportunity scores, and predictor labels.
3. Sorts symbol results by `next_day_score` descending to form `next_day_results`.
4. Saves output candidate files:
   - `reports/next_day_candidates.csv` (Primary next-day targets)
   - `reports/opportunity_ranking.csv` (Full ranking)
   - `reports/swing_candidates.csv` (Swing targets)
   - `reports/dashboard.html` (Interactive UI)
   - `reports/archive/opportunity_ranking_YYYYMMDD_HHMMSS.csv` (Timestamped archive)
5. Saves run signals to SQLite (`data/praecursor.db` or `config/praecursor.db`).
6. Triggers `AccuracyTracker().update_historical_outcomes()`, which evaluates the previous trading day's top 8 candidates against today's intraday high/close prices and updates `reports/archive/accuracy_history_archive.csv`.

### 5.2 Edge Cases & Data Timing at 5 PM
- **Market Close Timing**: EGX trading sessions end at 2:30 PM EET. By 5:00 PM EET, daily bar data is fully settled.
- **Data Availability Fallback**: If primary data source (TradingView) has not updated today's candle yet, `AccuracyTracker` leaves outcome evaluation as **pending** (`next_bar` is None) without throwing an error.

---

## 6. Audit of Manual Execution Trigger Support

### 6.1 Current Trigger Mechanisms
1. `python tools/run_autonomous_pipeline.py`
   - Supports `--dry-run-telegram` flag.
   - Executes full 4-stage pipeline.
2. `Daily Praecursor Update.bat`
   - Intended as a user shortcut.
   - Currently runs `python tools/run_scanner.py` directly, skipping retraining, dashboard generation, and Telegram.
3. `register_task.ps1` & `tools/register_scheduled_task.ps1`
   - PowerShell scripts for Task Scheduler registration.

### 6.2 Manual Execution Gaps
- Lack of CLI arguments in `run_autonomous_pipeline.py` for:
  - `--force`: Force execution even on weekends/holidays.
  - `--date YYYY-MM-DD`: Run pipeline as-of a specific date.
  - `--skip-stages`: Ability to skip specific stages (e.g. skip retraining during manual test runs).

---

## 7. Summary of Gaps, Edge Cases, and Recommended Hardening Fixes

| # | Gap / Vulnerability | Impact | Recommended Hardening Fix | Target Files |
|---|---------------------|--------|---------------------------|--------------|
| G1 | Root `register_task.ps1` points to interactive `Daily Praecursor Update.bat` | Scheduled task hangs indefinitely on `pause` statement in background session | Update `register_task.ps1` to execute `tools/run_autonomous_pipeline.py` directly via Python, with Sun–Thu schedule | `register_task.ps1`, `tools/register_task.ps1` |
| G2 | `Daily Praecursor Update.bat` contains interactive commands (`pause`, `start http://`) | Task Scheduler process hangs or fails in headless environment | Create a dedicated `run_headless_pipeline.bat` or clean up batch script for automated runs | `Daily Praecursor Update.bat`, `tools/run_pipeline.bat` |
| G3 | No network retry logic in `run_autonomous_pipeline.py` | Transient network timeouts abort pipeline on Stage 1 | Implement stage-level retry loop (3 retries with 10s backoff) in `run_stage()` or `run_pipeline()` | `tools/run_autonomous_pipeline.py` |
| G4 | No explicit weekend/holiday logging or check in Python pipeline | Execution on Friday/Saturday runs scanner needlessly without explicit skip/process logging | Add `is_egx_trading_day()` utility to check Sun–Thu & market holidays, logging explicit `PROCESSING` or `SKIPPED` status | `tools/run_autonomous_pipeline.py`, `src/praecursor/utils/calendar.py` |
| G5 | CLI arguments missing for manual override/backtesting | Harder to test or manually trigger pipeline for past dates or force weekend runs | Add `--force`, `--date`, `--skip-retrain` arguments to `run_autonomous_pipeline.py` | `tools/run_autonomous_pipeline.py` |

---

## 8. Verification Plan

To verify Requirement R2 hardening fixes once implemented:

### 8.1 Automated Unit & E2E Tests
1. **Task Scheduler Registration Test**:
   ```bash
   pytest tests/e2e/test_r1_scheduling.py -v
   ```
   - Verify task registers with `run_autonomous_pipeline.py` and schedule `Sun-Thu 17:00`.
   - Verify non-interactive execution without prompts.

2. **Weekend Skip & Explicit Logging Test**:
   - Execute `run_autonomous_pipeline.py` with mock date set to a Friday/Saturday.
   - Verify stdout/log contains: `[INFO] SKIPPED: Today (2026-08-07, Friday) is an EGX weekend day. Skipping pipeline.`
   - Verify exit code `0`.

3. **Network Recovery & Retry Test**:
   - Mock network failure on 1st and 2nd attempt of Stage 1, success on 3rd.
   - Verify pipeline retries and completes successfully.

4. **Manual Trigger CLI Test**:
   - Run `python tools/run_autonomous_pipeline.py --force --dry-run-telegram`.
   - Verify full 4-stage pipeline execution completing with exit code `0`.
