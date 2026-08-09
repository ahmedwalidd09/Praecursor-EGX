## 2026-08-08T11:24:18Z
You are teamwork_preview_worker assigned to fix test suite imports and DB auto-initialization error handling in Praecursor-EGX.

Working directory: C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\.agents\worker_m2_gen2
Original Request File: C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\.agents\ORIGINAL_REQUEST.md
Scope Document: C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\.agents\orchestrator\PROJECT.md
Challenger Handoff: C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\.agents\challenger_pipeline_2\handoff.md

Mandatory Steps:
1. Read ORIGINAL_REQUEST.md, PROJECT.md, and Challenger Handoff.
2. Edit `src/praecursor/storage/signal_history.py`:
   - In `SignalHistoryStore.latest_ranks()`, catch `sqlite3.OperationalError` (such as `no such table: scanner_runs`) or call `self.initialize()` to ensure required tables exist before querying. Return `None` or `[]` cleanly when database is uninitialized or table is missing.
3. Edit `src/praecursor/backtesting/engine.py` and `tests/test_swing.py`:
   - Fix line 9 of `src/praecursor/backtesting/engine.py` and line 5 of `tests/test_swing.py` which attempt to import `from praecursor.scoring.swing import calculate_swing_prediction`. Inspect the codebase (e.g. `src/praecursor/scoring/`) to resolve the correct module path or remove obsolete import references so `pytest tests/` collects and executes tests without `ModuleNotFoundError`.
4. Verification:
   - Run `pytest` to confirm test suite collection passes cleanly without `ModuleNotFoundError`.
   - Run `python tools/regenerate_dashboard.py` (verify exit code 0).
   - Run `python tools/run_autonomous_pipeline.py --date 2026-08-01` (verify exit code 0).
5. Write handoff report `handoff.md` and `changes.md` in `C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\.agents\worker_m2_gen2`.
