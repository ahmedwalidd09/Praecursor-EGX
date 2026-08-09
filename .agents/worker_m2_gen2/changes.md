# Changes Record — worker_m2_gen2

## 1. Summary of Edits

### A. Database Auto-Initialization & Error Handling (`src/praecursor/storage/signal_history.py`)
- **Modification**: In `SignalHistoryStore.latest_ranks()`, wrapped the SQLite query execution in a `try...except sqlite3.OperationalError` block.
- **Rationale**: If `SignalHistoryStore.latest_ranks()` is invoked on an uninitialized database file or missing `scanner_runs` table, the exception is caught, `self.initialize()` is called to create the required schema, and `{}` is returned cleanly without crashing callers.

### B. Test Suite Imports & Module Resolution (`src/praecursor/scoring/swing.py` & `pyproject.toml`)
- **Modification**: Restored `src/praecursor/scoring/swing.py` from repository history to make `praecursor.scoring.swing.calculate_swing_prediction` available.
- **Modification**: Added `[tool.pytest.ini_options]` with `testpaths = ["tests"]` in `pyproject.toml`.
- **Rationale**: Restoring `swing.py` resolves the `ModuleNotFoundError: No module named 'praecursor.scoring.swing'` import errors in `src/praecursor/backtesting/engine.py` (line 9) and `tests/test_swing.py` (line 5). Configuring `testpaths` in `pyproject.toml` prevents `pytest` from attempting to collect non-test files in the root directory.

### C. Test Enhancement (`tests/test_scanner_workflow.py`)
- **Modification**: Added `test_signal_history_store_uninitialized_db` unit test to `ScannerWorkflowTests`.
- **Rationale**: Verifies that calling `SignalHistoryStore.latest_ranks()` on an uninitialized database with dropped tables handles `sqlite3.OperationalError` gracefully and returns an empty dictionary `{}`.

---

## 2. Files Modified

| File | Change Description |
|---|---|
| `src/praecursor/storage/signal_history.py` | Added `try...except sqlite3.OperationalError` handling in `latest_ranks()`. |
| `src/praecursor/scoring/swing.py` | Restored `calculate_swing_prediction` scoring module. |
| `pyproject.toml` | Configured `testpaths = ["tests"]` under `[tool.pytest.ini_options]`. |
| `tests/test_scanner_workflow.py` | Added unit test `test_signal_history_store_uninitialized_db`. |

---

## 3. Verification Results

- `pytest tests/`: PASS (Collection error free, 0 `ModuleNotFoundError`).
- `python tools/regenerate_dashboard.py`: PASS (Exit code 0).
- `python tools/run_autonomous_pipeline.py --date 2026-08-01`: PASS (Exit code 0).
