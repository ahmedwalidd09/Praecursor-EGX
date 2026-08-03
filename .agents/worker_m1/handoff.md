# Handoff Report: Milestone 1 (Intraday Target Verification & Historical Archiving)

## 1. Observation

### Code Modifications & Additions
1. **`src/praecursor/analysis/accuracy_tracker.py`**:
   - Updated `update_historical_outcomes()`:
     - Target hit evaluation logic replaced with strict verification:
       ```python
       next_day_hit = 1 if high >= target else 0
       ```
     - Removed the `is_solid_gain = ((high - latest_close) / latest_close) >= 0.025` fallback which previously marked any +2.5% intraday gain as a HIT even when `high < next_day_target`.
     - Intraday high comparison ensures that if `high >= target_price`, it is recorded as a `HIT` (`next_day_hit = 1`) even if closing price `close < target_price`.
     - Added max return tracking calculation `next_day_max_return = ((high - latest_close) / latest_close * 100.0)` if `latest_close > 0` else `0.0`.
     - Upserts into `scanner_signal_outcomes` with `next_day_max_return` column.
     - Added call to `self.export_accuracy_history_archive()` at the end of `update_historical_outcomes()`.
   - Added method `export_accuracy_history_archive(self, export_path=None)`:
     - Generates `reports/archive/accuracy_history_archive.csv`.
     - Maintains running total accuracy metrics (`cumulative_total`, `cumulative_hits`, `cumulative_accuracy_pct`) across all evaluated historical runs without overwriting prior records.

2. **`src/praecursor/storage/signal_history.py`**:
   - Added `next_day_max_return REAL` column definition to `scanner_signal_outcomes` table schema.
   - Added safe migration in `SignalHistoryStore.initialize()`:
     ```python
     outcome_columns = [
         "next_day_max_return REAL DEFAULT 0"
     ]
     for col in outcome_columns:
         try:
             connection.execute(f"ALTER TABLE scanner_signal_outcomes ADD COLUMN {col}")
         except sqlite3.OperationalError:
             pass
     ```

3. **`tests/test_accuracy_tracker.py`**:
   - Created comprehensive unit tests:
     - `test_intraday_high_hits_target_even_when_close_is_lower`: Validates candidate target hit when intraday high reaches target price even if close is lower.
     - `test_intraday_high_misses_target_even_if_over_2_point_5_percent`: Validates candidate target miss when intraday high fails to reach target price, even if intraday gain > 2.5%.
     - `test_running_updater_multiple_times_appends_and_maintains_baseline_count`: Validates that running updater multiple times appends to history archive CSV and maintains the 16 baseline evaluation records count without duplicates.

4. **`reports/archive/accuracy_history_archive.csv`**:
   - Generated cumulative historical accuracy archive CSV file.

### Verification Commands Executed
- `python -m unittest tests/test_accuracy_tracker.py` — Passed (3/3 tests OK in 0.052s).
- `python -m unittest discover tests` — Passed (all unit tests OK).

---

## 2. Logic Chain

1. **Target Verification (R2)**:
   - *Observation*: Previously in `accuracy_tracker.py`, line 96-97 set `is_solid_gain = ((high - latest_close) / latest_close) >= 0.025`, and `next_day_hit = 1 if (high >= target or is_solid_gain) else 0`.
   - *Reasoning*: This fallback caused signals with aggressive targets (e.g. +7.5%) to be marked as HITs whenever intraday high reached +2.5%, diluting verification integrity. By replacing this with `next_day_hit = 1 if high >= target else 0`, a candidate is marked as a HIT if and only if `intraday_high >= target_price`. If `high >= target_price`, it is recorded as a `HIT` regardless of closing price `close`.

2. **Cumulative Archiving (R3)**:
   - *Observation*: Baseline consists of 16 top candidates across 2 scanner runs (8 candidates from 2026-08-01 run 25 + 8 candidates from 2026-08-02 run 57). `scanner_signal_outcomes` table has `UNIQUE(run_id, symbol)` constraint.
   - *Reasoning*: `update_historical_outcomes()` executes an `UPSERT` (`ON CONFLICT(run_id, symbol) DO UPDATE SET...`), preserving existing historical outcome rows and adding new ones without creating duplicate records on repeated execution.
   - *Reasoning*: `export_accuracy_history_archive()` queries `scanner_signal_outcomes` chronologically and writes running total metrics (`cumulative_total`, `cumulative_hits`, `cumulative_accuracy_pct`) to `reports/archive/accuracy_history_archive.csv`.

---

## 3. Caveats

No caveats. All requirements R2 and R3 have been implemented, tested, and verified against the repository codebase.

---

## 4. Conclusion

- Requirement R2 (Intraday Target Verification) is fully implemented in `src/praecursor/analysis/accuracy_tracker.py`.
- Requirement R3 (Cumulative Historical Archive) is fully implemented in `src/praecursor/analysis/accuracy_tracker.py` and `src/praecursor/storage/signal_history.py`.
- 16 baseline evaluation records across daily scanner runs are preserved with persistent SQLite appending and cumulative CSV export.
- 100% test pass rate achieved across all unit test suites.

---

## 5. Verification Method

### Test 1: Unit Test Verification
Run:
```bash
python -m unittest tests/test_accuracy_tracker.py
```
Expected output:
```
Ran 3 tests in ... OK
```

### Test 2: Full Project Test Suite Discovery
Run:
```bash
python -m unittest discover tests
```
Expected output:
```
OK
```

### Test 3: CSV Archive Verification
Inspect `reports/archive/accuracy_history_archive.csv`:
- Check column headers: `signal_date,run_id,symbol,latest_close,next_day_target,next_day_label,next_day_hit,next_day_return,next_day_max_return,cumulative_total,cumulative_hits,cumulative_accuracy_pct`
- Confirm `cumulative_total` increases monotonically across evaluated records.
