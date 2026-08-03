## 2026-08-03T13:23:10Z

You are Worker 3 for Praecursor-EGX Milestone 3 (Autonomous 5 PM Task Scheduler Integration & Automation).
Working directory: C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\.agents\worker_m3
Project root: C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX
Explorer 3 Report: C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\.agents\explorer_3\handoff.md
Scope document: C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\.agents\orchestrator\PROJECT.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Task:
Implement Requirement R1 (Autonomous 5 PM Scheduling & Pipeline Automation).

Detailed Instructions:
1. **Headless Autonomous Pipeline Runner (`tools/run_autonomous_pipeline.py`)**:
   - Create non-interactive python runner that executes:
     - Stage 1: Daily Scanner & Outcome Tracking (`tools/run_scanner.py`).
     - Stage 2: Model Retraining (`tools/retrain_models.py`).
     - Stage 3: Dashboard Regeneration (`tools/regenerate_dashboard.py`).
     - Stage 4: Telegram Summary Broadcast (`tools/send_telegram_report.py`).
   - Implement file logging to `logs/scheduled_pipeline_YYYYMMDD.log`.
   - Propagate exit code (0 on success, non-zero on failure) without interactive pauses (`pause`) or GUI popups (`start http://`).

2. **Task Scheduler PowerShell Installer (`tools/register_scheduled_task.ps1`)**:
   - Create PowerShell script that registers Windows Scheduled Task `Praecursor-EGX Daily Scanner`.
   - Schedule: Weekly on **Sunday, Monday, Tuesday, Wednesday, Thursday** at **17:00** (5:00 PM).
   - Action: Executes `python.exe` with `tools/run_autonomous_pipeline.py` and working directory set to project root.
   - Settings: Allow start on battery, restart on failure, 30 min time limit.

3. **1-Click Batch Wrapper (`tools/register_scheduled_task.bat`) & Uninstaller (`tools/unregister_scheduled_task.ps1`)**:
   - Create batch file calling `register_scheduled_task.ps1` with `powershell -ExecutionPolicy Bypass`.
   - Create uninstaller script `unregister_scheduled_task.ps1`.

4. **Verification**:
   - Write tests in `tests/test_scheduled_task.py` verifying script creation, parameter formatting, and headless pipeline exit code behavior.
   - Test execution via `python tools/run_autonomous_pipeline.py` and `powershell -ExecutionPolicy Bypass -File tools/register_scheduled_task.ps1`.
   - Document commands and test results in `C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\.agents\worker_m3\handoff.md`.

Send a message to parent when complete.
