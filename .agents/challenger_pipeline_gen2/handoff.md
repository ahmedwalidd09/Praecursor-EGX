# Empirical Handoff Report — Pipeline Execution & Network Isolation (Iteration 2)

**Agent Role**: EMPIRICAL CHALLENGER (`challenger_pipeline_gen2`)  
**Verdict**: `REQUEST_CHANGES`  
**Timestamp**: 2026-08-08T11:40:00Z  

---

## 1. Observation

Empirical testing was conducted against the `Praecursor-EGX` repository. Below are verbatim outputs and specific line references for each mandatory test case.

### 1. Pytest Suite Execution (`pytest tests/`)
- **Command**: `pytest tests/`
- **Result**: **FAILED** (Exit code `1`)
- **Summary**: 87 passed, 9 failed in 603.97s (10:03).
- **Failing Tests & Verbatim Error Details**:
  1. `tests/test_accuracy_tracker.py` (3 failures):
     - `TestAccuracyTracker::test_intraday_high_hits_target_even_when_close_is_lower`
     - `TestAccuracyTracker::test_intraday_high_misses_target_even_if_over_2_point_5_percent`
     - `TestAccuracyTracker::test_running_updater_multiple_times_appends_and_maintains_baseline_count`
     - **Error Trace**:
       ```text
       E sqlite3.OperationalError: table scanner_signals has no column named swing_score
       tests\test_accuracy_tracker.py:37: OperationalError
       ```
  2. `tests/test_challenger_2_empirical.py` (3 failures):
     - `TestChallenger2Empirical::test_csv_export_prevents_duplicate_candidates`
     - `TestChallenger2Empirical::test_intraday_high_below_target_is_miss`
     - `TestChallenger2Empirical::test_intraday_high_reaching_target_is_hit_even_if_close_is_lower`
     - **Error Trace**:
       ```text
       E sqlite3.OperationalError: table scanner_signals has no column named swing_score
       tests\test_challenger_2_empirical.py:53: OperationalError
       ```
  3. `tests/test_telegram.py` (1 failure):
     - `TelegramFormatterTests::test_formatter_contains_candidate_sections`
     - **Error Trace**:
       ```text
       E TypeError: ScannerWorkflow.run() got an unexpected keyword argument 'swing_report_path'
       tests\test_telegram.py:31: TypeError
       ```
  4. `tests/test_scoring.py` (1 failure):
     - `OpportunityScorerTests::test_scorer_returns_components_and_label_inputs`
     - **Error Trace**:
       ```text
       E AssertionError: 'Close > EMA20' not found in {'Rel Strength', 'Momentum20', 'MFI', 'Turnover', 'Force Index', 'RSI Rebound', 'RSI14 momentum', 'CMF', 'Fisher', 'Elder Ray', 'BBW', 'Relative Volume20', 'Donchian', 'EMA20 Reclaim', 'Breakout setup', 'MACD confirmation', 'Momentum5', 'Ichimoku', 'Limit Up', 'VWAP Mom', 'Keltner', 'StochRSI', 'SuperTrend', 'MTF Trend', 'Vol Spike', 'ADX', 'MACD Imp', 'ROC10', 'EMA Alignment', 'Williams %R', 'VPOC'}
       tests\test_scoring.py:17: AssertionError
       ```
  5. `tests/e2e/test_tier4_scenarios.py` (1 failure):
     - `TestTier4Scenarios::test_scenario_scheduled_task_lifecycle`

---

### 2. Dashboard Regeneration (`python tools/regenerate_dashboard.py`)
- **Command**: `python tools/regenerate_dashboard.py`
- **Result**: **PASSED** (Exit code `0`)
- **Log Output**:
  ```text
  INFO:__main__:Instantly regenerating dashboard from the latest database scan...
  INFO:__main__:Dashboard instantly regenerated from history!
  ```

---

### 3. Autonomous Pipeline Execution (`python tools/run_autonomous_pipeline.py --date 2026-08-01`)
- **Command**: `python tools/run_autonomous_pipeline.py --date 2026-08-01`
- **Result**: **PASSED** (Exit code `0`)
- **Log Output**:
  ```text
  2026-08-08 14:31:37,735 [INFO] ==================================================
  2026-08-08 14:31:38,221 [INFO] Praecursor-EGX Autonomous Daily Pipeline Started
  2026-08-08 14:31:38,222 [INFO] Project Root: C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX
  2026-08-08 14:31:38,223 [INFO] Log File: C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\logs\scheduled_pipeline_20260801.log
  2026-08-08 14:31:38,223 [INFO] Target Date: 2026-08-01
  2026-08-08 14:31:38,223 [INFO] ==================================================
  2026-08-08 14:31:38,223 [INFO] SKIPPED: Non-trading day (2026-08-01) - skipping automated scan.
  ```

---

### 4. Uninitialized/Deleted Database Resilience (`SignalHistoryStore.latest_ranks()`)
- **Script**: `.agents/challenger_pipeline_gen2/verify_signal_store.py`
- **Result**: **PASSED**
- **Log Output**:
  ```text
  --- Test 1: Non-existent file path ---
  Latest ranks on fresh empty DB: {}
  --- Test 2: Table dropped post-init ---
  Latest ranks after table drop: {}
  --- Test 3: File deleted on disk ---
  Latest ranks after file delete: {}
  ALL SIGNAL_HISTORY_STORE TESTS PASSED SUCCESSFULLY!
  ```

---

### 5. Network Isolation & API Credit Guard
- **Fixture**: `block_network_access` in `tests/conftest.py` line 22-46.
- **Verification**: `tests/test_network_isolation.py` PASSED.
- **Credit Usage**: 0 live API credit usage confirmed across all test runs due to socket-level interception.

---

## 2. Logic Chain

1. Worker 3 claimed in `handoff.md` line 79 that `pytest tests/` succeeded with 0 `ModuleNotFoundError` errors. However, full execution of `pytest tests/` fails with 9 test failures across 5 test modules.
2. The primary root cause of 6 test failures (`test_accuracy_tracker.py` and `test_challenger_2_empirical.py`) is schema mismatch: test helpers execute raw `INSERT INTO scanner_signals` including columns `swing_score`, `swing_label`, and `swing_stop_loss`. However, `SIGNAL_HISTORY_SCHEMA` in `src/praecursor/storage/signal_history.py` (lines 24-41) does not define these columns.
3. `test_telegram.py` line 31 passes `swing_report_path` to `ScannerWorkflow.run()`, which causes a `TypeError` because `ScannerWorkflow.run()` parameters were refactored.
4. `test_scoring.py` line 17 asserts `'Close > EMA20'` in component names, but `OpportunityScorer` now outputs `'EMA20 Reclaim'`.
5. Because the project requirement states that `pytest tests/` must collect and pass with exit code `0`, the overall verdict must be `REQUEST_CHANGES`.

---

## 3. Caveats

- CLI pipeline scripts (`regenerate_dashboard.py` and `run_autonomous_pipeline.py`) run cleanly and exit with code `0`.
- Missing database handling in `SignalHistoryStore.latest_ranks()` is robust against missing files and dropped tables.
- Network isolation successfully blocked external network calls.

---

## 4. Conclusion

**Verdict**: `REQUEST_CHANGES`

The backend scripts (`tools/regenerate_dashboard.py` and `tools/run_autonomous_pipeline.py`) and network isolation fixture pass successfully. However, `pytest tests/` fails with exit code `1` due to 9 broken tests resulting from schema column mismatches (`swing_score`), signature mismatches (`swing_report_path`), indicator component name drift (`Close > EMA20`), and scheduled task scenario failure.

---

## 5. Verification Method

To reproduce these findings independently:

1. **Run full pytest suite**:
   ```powershell
   pytest tests/
   ```
   *Expected outcome*: Exits with code `1` and outputs 9 failures.

2. **Verify SignalHistoryStore edge case test**:
   ```powershell
   python .agents/challenger_pipeline_gen2/verify_signal_store.py
   ```
   *Expected outcome*: Exits with code `0` confirming DB fallback resilience.

3. **Verify Dashboard Regeneration**:
   ```powershell
   python tools/regenerate_dashboard.py
   ```
   *Expected outcome*: Exits with code `0`.

4. **Verify Autonomous Pipeline (Non-trading day)**:
   ```powershell
   python tools/run_autonomous_pipeline.py --date 2026-08-01
   ```
   *Expected outcome*: Exits with code `0` logging `SKIPPED: Non-trading day`.
