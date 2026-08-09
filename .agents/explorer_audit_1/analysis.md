# Comprehensive Analysis: Accuracy Tracker (R1) & History Archive Completeness (R4)

**Agent:** explorer_audit_1  
**Date:** 2026-08-07  
**Target Components:**
- `src/praecursor/analysis/accuracy_tracker.py`
- `reports/archive/accuracy_history_archive.csv`
- `database/praecursor.db`

---

## 1. Executive Summary

This investigation audited the accuracy tracking system (`accuracy_tracker.py`) and historical archive (`accuracy_history_archive.csv`) for Egyptian Exchange (EGX) predictions under requirements R1 and R4.

**Key Findings:**
1. **Archive Completeness Deficit (R4)**: `accuracy_history_archive.csv` currently contains **16 records** across 2 trading dates (`2026-08-01` and `2026-08-02`, 8 candidates each). The requirement specifies **~40 records** (8 per day over 5 days).
2. **Missing Day Cause**: `2026-08-03` has a scanner run (Run ID 62) in `database/praecursor.db`, but its outcomes were skipped because `source_prices` lacks next-day (`2026-08-04`) price data. Dates prior to `2026-08-01` (e.g. `2026-07-29`, `2026-07-30`) or after `2026-08-03` lack scanner runs in `database/praecursor.db`.
3. **Target Verification Logic (R1)**: Target verification in `accuracy_tracker.py:99` correctly evaluates `next_day_hit = 1 if high >= target else 0`, matching Requirement R2/R1 (intraday high reaching target counts as a HIT even if close is lower).
4. **Duplicate Prevention Logic**: Duplicate prevention relies on SQLite `UNIQUE(run_id, symbol)` constraints in `scanner_signal_outcomes` and `export_accuracy_history_archive()` re-generating the CSV from SQLite data.
5. **Join Fragility Bug**: `export_accuracy_history_archive()` joins `scanner_signal_outcomes` with `top8` candidates on `run_id` and `symbol`. If an outcome exists under a non-latest `run_id` for a given date, `latest_close` and `next_day_target` default to `0.0`.

---

## 2. Current CSV Audit (`reports/archive/accuracy_history_archive.csv`)

- **Total Rows**: 16 data rows (+ 1 header row).
- **Date Breakdown**:
  - `2026-08-01` (Run ID 25): 8 candidate records (WKOL, ODIN, EALR, AFMC, PHAR, BIOC, AALR, CEFM).
  - `2026-08-02` (Run ID 57): 8 candidate records (ASCM, GTEX, AMII, HBCO, UTOP, ADRI, MOSC, EGS48271C018-EGP).
- **Duplicates**: 0 duplicate `(signal_date, symbol)` pairs in the current file.
- **Cumulative Totals**:
  - Row 1: `cumulative_total` = 1, `cumulative_hits` = 1, `cumulative_accuracy_pct` = 100.0%
  - Row 16: `cumulative_total` = 16, `cumulative_hits` = 8, `cumulative_accuracy_pct` = 50.0%

---

## 3. Detailed Audit of `accuracy_tracker.py`

### 3.1 Intraday Target Verification (`update_historical_outcomes`)
- **Location**: `src/praecursor/analysis/accuracy_tracker.py`, lines 70-103
- **Logic**:
  - `target` is read from `scanner_signals.next_day_target`. If `target <= 0`, it falls back to `latest_close`.
  - Next day bar is fetched via:
    ```sql
    SELECT trade_date, MAX(high) as high, MIN(low) as low, close
    FROM source_prices
    WHERE ticker = ? AND trade_date > ?
    GROUP BY trade_date
    ORDER BY trade_date ASC
    LIMIT 1
    ```
  - `next_day_hit = 1 if high >= target else 0`.
- **Verdict**: Correct logic for R1/R2 intraday high comparison.

### 3.2 Duplicate Prevention & Backfilling Bugs
- **Location**: `src/praecursor/analysis/accuracy_tracker.py`, lines 37-60, 105-117, 142-163
- **Bug 1: Next-Bar Lookahead Missing Data Skip**:
  - Lines 88-90: If `next_bar` is None (no future price bar in `source_prices`), `update_historical_outcomes()` executes `continue`, leaving candidate outcomes unpopulated.
  - When price data for subsequent days is added, running `update_historical_outcomes()` will process these pending candidates.
- **Bug 2: Query Joining `top8` on `run_id`**:
  - Lines 142-163 (`export_accuracy_history_archive`):
    ```sql
    WITH day_runs AS (
        SELECT MAX(id) as run_id, date(generated_at) as run_date
        FROM scanner_runs
        GROUP BY date(generated_at)
    ),
    top8 AS (
        SELECT s.run_id, s.symbol, s.next_day_target, s.latest_close,
               ROW_NUMBER() OVER(PARTITION BY s.run_id ORDER BY s.rank ASC) as rn
        FROM scanner_signals s
        JOIN day_runs dr ON s.run_id = dr.run_id
    )
    SELECT o.signal_date, o.run_id, o.symbol, ...
    FROM scanner_signal_outcomes o
    LEFT JOIN top8 t ON t.run_id = o.run_id AND t.symbol = o.symbol
    ```
  - If outcomes in `scanner_signal_outcomes` were created under an earlier `run_id` on `signal_date` (not `MAX(id)`), `LEFT JOIN top8` fails to match on `t.run_id = o.run_id`, resulting in `latest_close = 0.0` and `next_day_target = 0.0` in the exported CSV.

---

## 4. Root Causes of R4 Deficit (~40 Target Records)

1. `database/praecursor.db` has scanner runs for only 3 calendar dates:
   - `2026-08-01` (25 runs) -> 8 candidates evaluated.
   - `2026-08-02` (32 runs) -> 8 candidates evaluated.
   - `2026-08-03` (5 runs) -> 0 candidates evaluated (because `2026-08-04` bars are missing in `source_prices`).
2. There are no scanner runs or outcome records in `database/praecursor.db` for days 4 and 5 (or earlier 5 trading days like `2026-07-28`, `2026-07-29`, `2026-07-30`).

---

## 5. Recommended Fix Strategy for Implementer

1. **Backfill 5 Trading Days in Database & Archive (R4)**:
   - Populate/backfill `scanner_runs` and `scanner_signals` for 5 consecutive trading days (e.g. `2026-07-28`, `2026-07-29`, `2026-07-30`, `2026-08-01`, `2026-08-02` or `2026-08-01` through `2026-08-05`).
   - Ensure `source_prices` has next-day price bars (`trade_date > run_date`) for all 5 trading days.
   - Execute `AccuracyTracker().update_historical_outcomes()` to generate 40 outcome records (8 candidates x 5 days).
2. **Harden `export_accuracy_history_archive()` Join (R1)**:
   - Update the export query in `accuracy_tracker.py` to join `top8` on `o.signal_date = dr.run_date AND o.symbol = t.symbol` or ensure outcome `run_id` matches the candidate run ID.
3. **Verify CSV Re-generation**:
   - Ensure `export_accuracy_history_archive()` produces a clean 40-record CSV with running totals (`1..40`), correct cumulative hits, and accurate `cumulative_accuracy_pct`.

---

## 6. Verification Plan

1. **Run Pytest Suite**:
   ```powershell
   pytest tests/e2e/test_r3_historical_archive.py
   pytest tests/e2e/test_r1_scheduling.py
   ```
2. **Execute Custom Audit Script**:
   Run `.agents/explorer_audit_1/deep_audit.py` to confirm:
   - CSV row count = 40.
   - 5 unique signal dates with 8 records each.
   - 0 duplicate `(signal_date, symbol)` pairs.
   - `cumulative_total` sequence from 1 to 40.
