# Soft Handoff Report: Requirement R2 Pipeline & Task Scheduler Audit

## 1. Observation

Direct observations from examining the codebase:

1. **`register_task.ps1` (Line 21)**:
   ```powershell
   if ([string]::IsNullOrWhiteSpace($ScriptPath)) {
       $ScriptPath = Join-Path $ProjectRoot "Daily Praecursor Update.bat"
   }
   ```
   Root `register_task.ps1` defaults to `Daily Praecursor Update.bat` and registers it via `schtasks /SC DAILY`.

2. **`Daily Praecursor Update.bat` (Lines 9 & 21)**:
   ```batch
   start "Praecursor Dashboard Server" cmd /k "..."
   ...
   pause
   ```
   Contains interactive GUI operations and a blocking `pause` command.

3. **`tools/register_scheduled_task.ps1` (Lines 39–63)**:
   ```powershell
   $ScriptPath = Join-Path $ProjectPath "tools\run_autonomous_pipeline.py"
   ...
   $Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday, Monday, Tuesday, Wednesday, Thursday -At $Time
   ```
   Points directly to Python runner with EGX trading day schedule (Sun–Thu).

4. **`tools/run_autonomous_pipeline.py` (Lines 44–71 & 102–170)**:
   ```python
   def run_stage(logger, stage_num, stage_name, cmd, cwd) -> bool:
       result = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
       ...
   ```
   Performs single-attempt `subprocess.run` calls without internal retries or backoff loops. Has no trading day / weekend check logic (`datetime.now().weekday()`).

5. **`tests/e2e/test_r1_scheduling.py` (Lines 11–66)**:
   Tests task registration via `register_task.ps1` and `tools/register_task.bat`, verifying `Daily Praecursor Update.bat` is in `schtasks /Query`.

---

## 2. Logic Chain

1. **Observation 1 & 2** show that the default Task Scheduler registration script (`register_task.ps1`) targets `Daily Praecursor Update.bat`. Because this `.bat` file ends with `pause` and launches interactive command windows, executing it headlessly via Task Scheduler will block indefinitely or fail in non-interactive Session 0.
2. **Observation 3** shows that a modern, proper headless registration script (`tools/register_scheduled_task.ps1`) already exists, targeting `tools/run_autonomous_pipeline.py` and scheduling execution for EGX trading days (Sun–Thu). However, the root `register_task.ps1` (which `test_r1_scheduling.py` tests) has not been updated to use this target.
3. **Observation 4** shows that `run_autonomous_pipeline.py` lacks stage-level retry logic for network timeouts and lacks explicit logging or skipping for non-trading days (weekends/holidays). If run on a Friday or Saturday, it executes the scanner unnecessarily without logging skip status.
4. **Observation 5** shows that existing unit/e2e tests check task registration against `Daily Praecursor Update.bat`. Updating `register_task.ps1` to target `tools/run_autonomous_pipeline.py` requires updating test expectations accordingly.

---

## 3. Caveats

- Task Scheduler execution was tested via `schtasks` query commands; live unattended 5 PM trigger behavior across Windows service accounts depends on system execution privileges.
- Official EGX market holiday calendar for future dates is not hardcoded in the repository; weekend logic (Friday/Saturday) is static.

---

## 4. Conclusion

Requirement R2 requires hardening across three key areas:
1. **Task Scheduler Alignment**: Standardize root `register_task.ps1` and `tools/register_task.ps1` to target `tools/run_autonomous_pipeline.py` (headless), replacing `Daily Praecursor Update.bat`, and schedule execution for EGX trading days (Sunday–Thursday).
2. **Network Resilience & Retry**: Add stage-level retry logic (3 attempts, 10s backoff) inside `run_autonomous_pipeline.py` for Stage 1.
3. **Explicit Weekend/Holiday Logging**: Add EGX trading day checking (`is_egx_trading_day()`) in `run_autonomous_pipeline.py` that explicitly logs `PROCESSING: EGX Trading Day` or `SKIPPED: Non-trading day (weekend/holiday)` and exits cleanly with code 0.

---

## 5. Verification Method

To verify R2 hardening implementation:
1. **Run E2E Scheduling Tests**:
   ```powershell
   pytest tests/e2e/test_r1_scheduling.py -v
   ```
2. **Verify Scheduled Task Target**:
   ```powershell
   powershell -ExecutionPolicy Bypass -File register_task.ps1 PraecursorTest 17:00
   schtasks /Query /TN PraecursorTest /V /FO LIST
   schtasks /Delete /TN PraecursorTest /F
   ```
   Confirm `Task To Run` points to `python.exe` executing `tools/run_autonomous_pipeline.py` (not `Daily Praecursor Update.bat`).
3. **Verify Non-Trading Day Logging**:
   Run pipeline with a weekend date context and inspect stdout/log file for explicit `SKIPPED: Non-trading day` message.

---

## Remaining Work (For Implementation Agent)

1. Update `register_task.ps1` (root) and `tools/register_task.ps1` to execute `tools/run_autonomous_pipeline.py` headlessly via Python.
2. Add EGX trading day helper and explicit weekend/holiday logging to `tools/run_autonomous_pipeline.py`.
3. Add retry loop with exponential backoff to `run_stage()` in `tools/run_autonomous_pipeline.py`.
4. Update `tests/e2e/test_r1_scheduling.py` assertions to match the new headless pipeline target.
