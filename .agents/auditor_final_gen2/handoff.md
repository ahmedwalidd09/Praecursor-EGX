# Forensic Audit Report

**Work Product**: Praecursor-EGX Iteration 2 Changes
**Working Directory**: `C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\.agents\auditor_final_gen2`
**Original Request File**: `C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\.agents\ORIGINAL_REQUEST.md`
**Scope Document**: `C:\Users\moody\.gemini\antigravity\scratch\Praecursor-EGX\.agents\orchestrator\PROJECT.md`
**Profile**: General Project (Demo Integrity Mode)
**Verdict**: INTEGRITY VIOLATION

---

## 1. Observation

Empirical evidence from static code analysis and full runtime execution of `pytest tests/`:

### A. Runtime Test Execution Results (`pytest tests/`)
Execution of `pytest tests/` failed with exit code 1. Out of 96 total test items collected, 88 passed and 8 failed:

1. **`sqlite3.OperationalError: table scanner_signals has no column named swing_score`**
   - **`tests/test_accuracy_tracker.py`**:
     - `test_intraday_high_hits_target_even_when_close_is_lower`: FAIL
     - `test_intraday_high_misses_target_even_if_over_2_point_5_percent`: FAIL
     - `test_running_updater_multiple_times_appends_and_maintains_baseline_count`: FAIL
   - **`tests/test_challenger_2_empirical.py`**:
     - `test_csv_export_prevents_duplicate_candidates`: FAIL
     - `test_intraday_high_below_target_is_miss`: FAIL
     - `test_intraday_high_reaching_target_is_hit_even_if_close_is_lower`: FAIL
   - **Root Cause**: `SIGNAL_HISTORY_SCHEMA` in `src/praecursor/storage/signal_history.py` defines `scanner_signals` without a `swing_score` column, causing database operations in `AccuracyTracker` tests to raise `sqlite3.OperationalError`.

2. **`TypeError: ScannerWorkflow.run() got an unexpected keyword argument 'swing_report_path'`**
   - **`tests/test_telegram.py`**:
     - `test_formatter_contains_candidate_sections`: FAIL
   - **Root Cause**: `ScannerWorkflow.run()` in `src/praecursor/workflows/scanner.py` does not accept the `swing_report_path` parameter expected by `test_telegram.py`.

3. **`AssertionError: 'Close > EMA20' not found in {'VWAP Mom', 'Limit Up', 'Momentum20', 'CMF', ...}`**
   - **`tests/test_scoring.py`**:
     - `test_scorer_returns_components_and_label_inputs`: FAIL
   - **Root Cause**: Component naming mismatch between `OpportunityScorer` in `src/praecursor/scoring/opportunity_score.py` and expected assertions in `test_scoring.py`.

---

### B. Summary of Failing Tests (8 Failed, 88 Passed)
```
FAILED tests/test_accuracy_tracker.py::TestAccuracyTracker::test_intraday_high_hits_target_even_when_close_is_lower
FAILED tests/test_accuracy_tracker.py::TestAccuracyTracker::test_intraday_high_misses_target_even_if_over_2_point_5_percent
FAILED tests/test_accuracy_tracker.py::TestAccuracyTracker::test_running_updater_multiple_times_appends_and_maintains_baseline_count
FAILED tests/test_challenger_2_empirical.py::TestChallenger2Empirical::test_csv_export_prevents_duplicate_candidates
FAILED tests/test_challenger_2_empirical.py::TestChallenger2Empirical::test_intraday_high_below_target_is_miss
FAILED tests/test_challenger_2_empirical.py::TestChallenger2Empirical::test_intraday_high_reaching_target_is_hit_even_if_close_is_lower
FAILED tests/test_scoring.py::OpportunityScorerTests::test_scorer_returns_components_and_label_inputs
FAILED tests/test_telegram.py::TelegramFormatterTests::test_formatter_contains_candidate_sections
```

---

## 2. Logic Chain

1. **Observation 1**: Full execution of `pytest tests/` returned exit code 1 with 8 failing test cases out of 96.
2. **Observation 2**: 6 tests failed due to a missing column (`swing_score`) in the SQLite table `scanner_signals` schema (`src/praecursor/storage/signal_history.py`).
3. **Observation 3**: 1 test failed due to an incompatible method signature (`swing_report_path` parameter missing from `ScannerWorkflow.run()`).
4. **Observation 4**: 1 test failed due to an assertion failure on score component names (`'Close > EMA20'`).
5. **Rule Application**: According to Forensic Integrity Audit rules, every mandatory check must pass empirically. A non-zero test suite exit code or any test failure constitutes a verification failure.
6. **Conclusion**: Because 8 automated test cases failed during full test execution (`pytest tests/`), the work product fails Phase 2 Behavioral Verification. Verdict is **`INTEGRITY VIOLATION`**.

---

## 3. Caveats

- Individual tool executions (`python tools/regenerate_dashboard.py` and `python tools/run_autonomous_pipeline.py --date 2026-08-01`) passed with exit code 0, but the core test suite contains schema and signature regressions preventing full test suite passage.

---

## 4. Conclusion

**Final Verdict**: **`INTEGRITY VIOLATION`**

The work product is REJECTED due to 8 failing tests in `pytest tests/` caused by database schema column omission (`swing_score`), missing keyword arguments (`swing_report_path`), and broken score component assertions.

---

## 5. Verification Method

To independently verify this failure:

1. **Execute full test suite**:
   ```bash
   python -m pytest tests/ -v
   ```
   *Expected Result*: Exit code 1 with 8 failed tests as detailed above.
