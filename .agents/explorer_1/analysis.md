# Praecursor-EGX Codebase Analysis & E2E Test Suite Preparation Report

**Date**: 2026-08-03  
**Author**: Explorer Subagent (`explorer_1`)  
**Target Project**: Praecursor-EGX (`C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX`)  

---

## 1. Executive Summary

This report presents a comprehensive codebase investigation of **Praecursor-EGX** to prepare for E2E Test Suite implementation. The investigation covers system entry points, database schemas, current scheduling mechanisms, accuracy tracking algorithms, historical archiving pipelines, data consensus engines, and test suite execution infrastructure corresponding to requirements **R1, R2, R3, and R4**.

---

## 2. Requirement-by-Requirement Analysis

### R1. Autonomous 5 PM Scheduling
- **Objective**: Create a Windows Scheduled Task that triggers daily updates and scanning automatically at 5:00 PM on trading days without manual intervention.
- **Code Locations Inspected**:
  - `Daily Praecursor Update.bat` (Root directory)
  - `tools/run_scanner.py`
  - `src/praecursor/cli/scanner.py`
- **Observations & Evidence**:
  - `Daily Praecursor Update.bat` currently exists at root. It launches the dashboard server (`python -m praecursor.cli.dashboard`), runs `python tools/run_scanner.py`, opens `http://127.0.0.1:8000`, and calls interactive `pause`.
  - **No automated Windows Task Scheduler registration script** (`.ps1` or `.bat`) currently exists in the repository.
- **Deficiencies & Implementation Requirements**:
  1. Create a Task Scheduler registration script (e.g. `tools/register_task.ps1` or `register_task.bat`) using `schtasks` or PowerShell `Register-ScheduledTask`.
  2. Configure trigger: 17:00 (5:00 PM) on trading days (Sunday-Thursday for EGX).
  3. Action command: Execute headless/non-interactive runner script (`python tools/run_scanner.py --non-interactive` or equivalent).
  4. Ensure task re-registration is idempotent (overwrites/updates without crashing) and provides clear messaging if administrator elevation is required.

---

### R2. Intraday Target Verification
- **Objective**: Verify if a stock's intraday high reached its specific target percentage (e.g. 7.5%) or calculated ATR target price (`entry_price * (1 + target_pct)`). If intraday high >= target, it must count as a **HIT** even if closing price is lower.
- **Code Locations Inspected**:
  - `src/praecursor/analysis/accuracy_tracker.py` (`update_historical_outcomes`, `get_accuracy_stats`)
  - `src/praecursor/scoring/next_day.py` (`calculate_next_day_prediction`, lines 268-272)
  - `src/praecursor/storage/signal_history.py` (`scanner_signal_outcomes` table)
- **Observations & Evidence**:
  - `AccuracyTracker.update_historical_outcomes()` (lines 76-97) queries `source_prices` table for `MAX(high) as high` on the trading day following `run_date`.
  - Hit evaluation logic: `next_day_hit = 1 if (high >= target or is_solid_gain) else 0`.
  - `target` is loaded from `scanner_signals.next_day_target` (calculated in `next_day.py` as `latest_close + 1.5 * ATR14`).
  - `next_day_return` records closing return: `(close_next - latest_close) / latest_close * 100.0`.
- **Deficiencies & Implementation Requirements**:
  1. The hit condition checks `high >= target`, but includes a fallback heuristic `is_solid_gain` (2.5% gain).
  2. Need explicit target verification rule: mark `next_day_hit = 1` (HIT) whenever `intraday_high >= target_price` (or `entry_price * (1 + target_pct)`), explicitly ignoring if `close_next` falls below `target_price`.
  3. Boundary conditions to test/handle: floating-point precision tolerances (e.g. 7.5000001%), zero ATR fallbacks, limit-up circuit breaker (+20%), stagnant zero-volume days, and NaN/negative price validation.

---

### R3. Cumulative Historical Archive
- **Objective**: Maintain a persistent, cumulative historical archive (`database/praecursor.db` table `scanner_signal_outcomes` / CSV) of daily hits/misses. Appends new daily evaluation records to retain a running total of accuracy percentage over time.
- **Code Locations Inspected**:
  - `database/praecursor.db` (Active SQLite database)
  - `src/praecursor/storage/signal_history.py` (`SignalHistoryStore`, `scanner_signal_outcomes`)
  - `src/praecursor/analysis/accuracy_tracker.py` (`get_accuracy_stats`)
- **Observations & Evidence**:
  - Active database: `database/praecursor.db` contains 144,367 source price rows, 57 scanner runs, 10,487 signals, and 8 outcomes currently populated for run 25 (`2026-08-01`).
  - `scanner_signal_outcomes` table schema: `UNIQUE(run_id, symbol)`, updated via `ON CONFLICT(run_id, symbol) DO UPDATE`.
  - Baseline dataset: 16 historical accuracy records expected (e.g. 2 past trading days x top 8 candidates per day = 16 records).
- **Deficiencies & Implementation Requirements**:
  1. Ensure initial baseline contains 16 historical outcome records (8 candidates/day x 2 baseline days).
  2. New scanner/updater runs must **append** new evaluation outcomes to `scanner_signal_outcomes` rather than overwriting past days.
  3. `get_accuracy_stats()` calculates running accuracy percentage over all cumulative archived records (`SUM(hits) / COUNT(*)`).
  4. Ensure idempotency when running updater multiple times on the same date/run ID so records are not duplicated or corrupted.

---

### R4. Data Source Consensus
- **Objective**: Cross-reference multiple independent data sources (TradingView, Mubasher, StockAnalysis, etc.) for both intraday highs and closing prices to prevent false or anomalous data from corrupting accuracy tracking.
- **Code Locations Inspected**:
  - `src/praecursor/consensus/price_consensus.py` (`PriceConsensusEngine`, `SourcePrice`, `PriceConsensusResult`)
  - `src/praecursor/collectors/tradingview_source.py` (`TradingViewSource` via `tvdatafeed`)
  - `src/praecursor/collectors/mubasher_source.py` (`MubasherSource` via web scraping)
  - `src/praecursor/workflows/scanner.py` (`_calculate_consensus`, `_fetch_consensus_results`)
- **Observations & Evidence**:
  - `PriceConsensusEngine` compares source prices against median close using a percentage tolerance (default 0.5%) and requires minimum agreeing sources (default 2 or 3).
  - `SourcePrice` currently records `source_name`, `symbol`, `trade_date`, `close`, `volume`. **It does not yet track `high` price!**
- **Deficiencies & Implementation Requirements**:
  1. Extend `SourcePrice` and `PriceConsensusEngine` to evaluate consensus for **both `high` and `close` prices**.
  2. In `ScannerWorkflow` and `AccuracyTracker`, cross-reference intraday highs from TradingView and Mubasher before assigning the final consensus high for target verification.
  3. Ensure log outputs explicitly state price comparisons between sources (e.g. `TradingView high=105.0, Mubasher high=105.2 -> Consensus high=105.1`).
  4. Reject single-source bar anomalies (e.g. TradingView 1-bar spike) when another source agrees on clean price data.

---

## 3. Test Environment & Suite Architecture

- **Test Infrastructure**:
  - Root directory contains `tests/` with 16 unit test modules.
  - `tools/run_tests.py` runs standard `unittest` discovery.
  - E2E Test Suite target framework: `pytest` executing tests in `tests/e2e/`.
- **E2E Scope Breakdown** (from `e2e_testing_orch/SCOPE.md`):
  - **Tier 1 (Feature Coverage - 20 tests)**:
    - 5 scheduling tests (`test_r1_*`)
    - 5 intraday target tests (`test_r2_*`)
    - 5 cumulative archive tests (`test_r3_*`)
    - 5 consensus logging/engine tests (`test_r4_*`)
  - **Tier 2 (Boundary & Corner Cases - 20 tests)**:
    - Task re-registration, float precision, 0 ATR, Limit Up, archive corruption, duplicate dates, consensus disagreement, HTTP timeouts.
  - **Tier 3 (Cross-Feature Combinations - 4 tests)**:
    - Scheduled append, consensus target verification, scheduled target evaluation, consensus archive logging.
  - **Tier 4 (Real-World Scenarios - 5 tests)**:
    - Multi-day pipeline, weekly trading simulation (16 -> 21 records), TradingView outage resilience, scheduled task lifecycle, rerun idempotency.
  - Total: **49 E2E Test Cases**.

---

## 4. Verification Methods

1. **Scheduling (R1)**: Execute PowerShell/Batch registration script, query `schtasks /query /tn "Praecursor-EGX Daily Scanner"`, verify trigger time = 17:00.
2. **Target Verification (R2)**: Run unit/E2E test where `latest_close=100.0`, `target=107.5`, `high=108.0`, `close=102.0`. Verify `next_day_hit == 1`.
3. **Cumulative Archive (R3)**: Inspect `database/praecursor.db` `scanner_signal_outcomes`. Execute updater across 2 consecutive runs; verify row count increases by 8 per run, retaining 16 baseline records.
4. **Consensus Engine (R4)**: Invoke `ScannerWorkflow` with TradingView and Mubasher mock sources; inspect stdout/log file to verify explicit multi-source fetch and high/close comparison logs.
5. **Test Suite Execution**: Execute `pytest tests/e2e -v` or `python tools/run_tests.py` and verify zero failures.
