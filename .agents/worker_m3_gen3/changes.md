# Summary of Changes

## Overview
Fixed database schema column omissions, workflow API signature mismatches, notification formatters, and test assertion mismatches across the Praecursor-EGX test suite and core modules.

## Files Modified

### 1. `src/praecursor/storage/signal_history.py`
- Added `swing_score REAL DEFAULT 0`, `swing_label TEXT DEFAULT ''`, and `swing_stop_loss REAL DEFAULT 0` columns to `SIGNAL_HISTORY_SCHEMA` table definition for `scanner_signals`.
- Added `swing_score`, `swing_label`, and `swing_stop_loss` to the `new_columns` list in `SignalHistoryStore.initialize()` to ensure clean migration on existing databases.
- Updated `SignalHistoryStore.save_run()` to insert `swing_score`, `swing_label`, and `swing_stop_loss` extracted safely from `symbol_result` (with default fallbacks).

### 2. `src/praecursor/workflows/scanner.py`
- Added `swing_prediction`, `swing_score`, `swing_label`, and `swing_stop_loss` properties to `SymbolScanResult`.
- Added `swing_results` property to `ScannerRunResult` to allow ranking symbols by swing score.
- Updated `ScannerWorkflow.run()` signature to accept `swing_report_path: Path | None = None` and `**kwargs`.

### 3. `src/praecursor/notifications/telegram.py`
- Updated `TelegramReportFormatter.format_scanner_result()` to render the `🎯 Swing Candidates` section as expected by notifications and test suites.

### 4. `tests/test_scoring.py`
- Updated component name assertion from `"Close > EMA20"` to `"EMA Alignment"` matching the exact component name produced by `OpportunityScorer`.

## Verification Results
- `pytest tests/`: All 96 tests passing with 0 failures and 0 errors.
- `python tools/regenerate_dashboard.py`: Completed cleanly with exit code 0.
- `python tools/run_autonomous_pipeline.py --date 2026-08-01`: Completed cleanly with exit code 0.
