# Backend Pipeline Execution Stability Audit

**Target Repository**: `Praecursor-EGX`  
**Audited Scripts**: `tools/regenerate_dashboard.py`, `tools/run_autonomous_pipeline.py`, `tools/run_scanner.py`, `src/praecursor/cli/scanner.py`, `src/praecursor/cli/telegram.py`, `tools/retrain_models.py`  
**Auditor**: `teamwork_preview_explorer` (`explorer_pipeline_2`)  
**Date**: 2026-08-08  

---

## 1. Executive Summary

An in-depth execution stability audit was performed on the backend pipeline execution of `Praecursor-EGX`. 
Specifically, the audit evaluated:
1. `python tools/regenerate_dashboard.py`
2. `python tools/run_autonomous_pipeline.py --date 2026-08-01` (and trading dates such as `--date 2026-08-02`).

### Core Findings
- **Critical Failure 1 (Pipeline CLI Argument Mismatch)**: `tools/run_autonomous_pipeline.py` passes `--date YYYY-MM-DD` to `tools/run_scanner.py`, but `praecursor/cli/scanner.py` does **not** recognize the `--date` argument. When executed on a trading day (or with `--date`), `run_scanner.py` crashes with `argparse.ArgumentError: unrecognized arguments: --date ...` (Exit Code 2). Stage 1 retries 3 times and fails, causing `run_autonomous_pipeline.py` to abort with **Exit Code 1**.
- **Critical Failure 2 (Non-Zero Exit on Empty DB in Regenerate Dashboard)**: `tools/regenerate_dashboard.py` exits with status code **1** if no scanner runs are found in the SQLite database (`if not latest_run: return 1`), violating the acceptance criterion that `python tools/regenerate_dashboard.py` must complete with exit code **0**.
- **Uncaught Exception Vulnerability in `regenerate_dashboard.py`**: `tools/regenerate_dashboard.py` lacks a top-level `try...except` wrapper. Operational errors (missing database tables, missing `reports/` directory, ISO string parsing issues in older Python runtimes, or null column values in database rows) result in uncaught Python stack traces.
- **Secondary Pipeline Crash Hazards**:
  - `tools/retrain_models.py` (Stage 2) crashes with `sqlite3.OperationalError` if database tables do not exist.
  - `tools/send_telegram_report.py` / `src/praecursor/cli/telegram.py` (Stage 4) raises `SystemExit` with exit code **1** if `load_latest_scan_result()` returns `None`.

---

## 2. Execution Flow Traces

### Trace 1: `python tools/regenerate_dashboard.py`

1. **Invocation**: Executed directly or from Stage 3 of `run_autonomous_pipeline.py`.
2. **Settings & Database Initialization**:
   - Instantiates `ScannerSettings.from_json()` and `SignalHistoryStore()`.
   - Opens connection `store._connect()` to SQLite DB (`database/praecursor.db`).
3. **Run Query**:
   - Executes `SELECT * FROM scanner_runs WHERE id IN (SELECT run_id FROM scanner_signals) ORDER BY id DESC LIMIT 1`.
   - **Crash Point 1.1**: If tables `scanner_runs` or `scanner_signals` do not exist in `praecursor.db`, SQLite raises uncaught `sqlite3.OperationalError: no such table: scanner_runs`.
   - **Crash Point 1.2**: If `latest_run` is `None` (empty database), the script executes line 54 `logger.error(...)` and line 55 `return 1`. In `sys.exit(main())`, this terminates the process with **exit code 1**.
4. **Data Reconstruction**:
   - Parses `generated_at = datetime.fromisoformat(latest_run["generated_at"])`.
   - **Crash Point 1.3**: `datetime.fromisoformat` can raise `ValueError` / `TypeError` on ISO strings ending with 'Z' on Python < 3.11 or malformed date inputs.
   - Loops over `scanner_signals` rows and reconstructs `OpportunityScore`, `PriceConsensusResult`, `NextDayPrediction`, and `MockSymbolScanResult`.
   - **Crash Point 1.4**: Null database columns (e.g. `latest_close=None` or `consensus_confidence=None`) cause `TypeError` during arithmetic operations (`row["latest_close"] * 1.05`).
5. **Dashboard Generation**:
   - Instantiates `ScannerRunResult` and calls `ScannerDashboardWriter().write(run_result)`.
   - `ScannerDashboardWriter.write()` writes HTML to `reports/dashboard.html`.

---

### Trace 2: `python tools/run_autonomous_pipeline.py --date 2026-08-01`

1. **CLI Parsing**: `main()` parses `--date 2026-08-01` into a `datetime.date(2026, 8, 1)` object (`parsed_date`).
2. **Trading Day Check**:
   - Calls `is_egx_trading_day(parsed_date)`.
   - `2026-08-01` is a Saturday (weekday index 5).
   - `is_egx_trading_day` returns `False`.
   - Pipeline logs: `SKIPPED: Non-trading day (2026-08-01) - skipping automated scan.` and returns **0**.
3. **Execution Trace on Trading Day (e.g., `--date 2026-08-02` or `--force`)**:
   - **Stage 1 (Daily Scanner)**:
     - `s1_cmd = [python_exe, "tools/run_scanner.py", "--date", "2026-08-02"]`.
     - `run_stage()` executes subprocess.
     - `tools/run_scanner.py` calls `praecursor.cli.scanner.main()`.
     - `praecursor.cli.scanner.parse_args()` uses `argparse.ArgumentParser` which does **not** recognize `--date`.
     - **Crash Point 2.1**: `argparse` exits with code 2 and prints: `run_scanner.py: error: unrecognized arguments: --date 2026-08-02`.
     - Subprocess returns exit code 2.
     - `run_stage` retries 3 times with backoff (10s, 20s) and fails completely.
     - `run_pipeline` logs `Stage 1 (Scanner) failed. Aborting downstream pipeline execution.` and returns **1**.

---

## 3. Comprehensive Crash Point & Vulnerability Inventory

| # | File / Component | Code Line / Area | Vulnerability / Failure Mechanism | Impact |
|---|---|---|---|---|
| 1 | `praecursor/cli/scanner.py` | `parse_args()` | CLI parser missing `--date` argument. Passes `--date` from `run_autonomous_pipeline.py`. | **Stage 1 fails with Exit Code 2**. Pipeline aborts with Exit Code 1. |
| 2 | `praecursor/cli/scanner.py` | `main()` | `main()` does not forward target date (`args.date`) to `workflow.run(end_date=...)`. | Historical date runs default to `date.today()` instead of requested date. |
| 3 | `tools/regenerate_dashboard.py` | Line 53–55 | `if not latest_run: return 1` returns 1 when database is unpopulated. | Command fails with exit code 1, violating acceptance criteria. |
| 4 | `tools/regenerate_dashboard.py` | `main()` | Lacks top-level `try...except Exception` handler. | Operational/schema/IO errors throw raw stack traces and crash script. |
| 5 | `tools/regenerate_dashboard.py` | Line 58 | `datetime.fromisoformat(latest_run["generated_at"])` without `.replace('Z', '+00:00')`. | `ValueError` on Python standard libraries parsing 'Z' suffix timestamps. |
| 6 | `tools/regenerate_dashboard.py` | Lines 68–121 | Unsafe dictionary access (`row["latest_close"]`, `row["consensus_confidence"]`) without null checks. | `TypeError` / `KeyError` if database columns contain `NULL` or missing schema keys. |
| 7 | `tools/retrain_models.py` | `load_data_from_db()` | Uncaught `sqlite3.OperationalError` if database tables `scanner_signals` or `scanner_signal_outcomes` do not exist. | Stage 2 crashes with `sqlite3.OperationalError`. |
| 8 | `src/praecursor/cli/telegram.py` | Line 87–88 | `if result is None: raise SystemExit("No scanner runs found in database.")` | Stage 4 fails with exit code 1 when DB has no runs. |
| 9 | `tools/regenerate_dashboard.py` & `src/praecursor/reporting/dashboard.py` | File Output | Directory `reports/` or `reports/archive/` may not exist before direct standalone invocation. | `FileNotFoundError` during HTML write. |

---

## 4. Remediation Strategy for the Worker

To ensure both `python tools/regenerate_dashboard.py` and `python tools/run_autonomous_pipeline.py --date 2026-08-01` execute with exit code 0 and zero uncaught stack traces, the Worker must implement the following targeted fixes:

### Change 1: Add `--date` Support to `src/praecursor/cli/scanner.py`
In `parse_args()` in `src/praecursor/cli/scanner.py`:
- Add argument `--date` (type `str`, default `None`, help `"Target scan date in YYYY-MM-DD format."`).
- Parse `args.date` using `datetime.strptime(args.date, "%Y-%m-%d").date()` if provided.
- In `main()`, pass `end_date=target_date` to `workflow.run(symbols=symbols, end_date=target_date)`.

### Change 2: Bulletproof `tools/regenerate_dashboard.py`
1. Wrap the execution in a top-level `try...except Exception as e` block.
2. In case of missing database, uninitialized tables, or `latest_run is None`:
   - Log a descriptive warning (e.g. `logger.warning("No historical runs found in database. Generating default empty dashboard.")`).
   - Construct a minimal default fallback `ScannerRunResult` with an empty `symbol_results` list (or default mock data).
   - Write the dashboard via `writer.write(fallback_run_result)`.
   - Ensure the function returns `0`.
3. Handle potential `None` values in SQLite dictionary rows using `.get("col", default)`.
4. Standardize ISO date parsing: `datetime.fromisoformat(latest_run["generated_at"].replace("Z", "+00:00"))`.
5. Ensure `reports/` directory exists before writing: `Path("reports").mkdir(parents=True, exist_ok=True)`.

### Change 3: Harden `tools/retrain_models.py`
In `load_data_from_db()`:
- Wrap database query in a `try...except sqlite3.OperationalError` block.
- Return an empty `pd.DataFrame(columns=["run_id", "symbol", "run_date", "target", "latest_close"])` if table is missing or query fails, allowing the synthetic model retraining to proceed cleanly without throwing stack traces.

### Change 4: Harden `src/praecursor/cli/telegram.py`
In `main()`:
- If `args.use_latest` or `args.dry_run` is set and `load_latest_scan_result()` returns `None`:
  - Print / log: `"No scan history found in database. Telegram summary skipped."`
  - Return `0` instead of raising `SystemExit` with exit code 1.

---

## 5. Verification Method for Implementation

After the Worker applies these remediations, verify with the following commands:

```bash
# Test 1: Direct regenerate dashboard (must return exit code 0 and generate reports/dashboard.html)
python tools/regenerate_dashboard.py
echo Exit Code: %ERRORLEVEL%

# Test 2: Non-trading date (Saturday, must return exit code 0 and log SKIPPED)
python tools/run_autonomous_pipeline.py --date 2026-08-01
echo Exit Code: %ERRORLEVEL%

# Test 3: Trading date (Sunday, must execute all 4 stages and return exit code 0)
python tools/run_autonomous_pipeline.py --date 2026-08-02
echo Exit Code: %ERRORLEVEL%
```
