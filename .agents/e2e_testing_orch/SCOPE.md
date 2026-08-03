# Scope: E2E Testing Track — Praecursor-EGX

## Architecture
- Product: Praecursor-EGX Automated Stock Screener & Breakout AI
- Entry points: `tools/run_scanner.py`, `tools/retrain_models.py`, `Daily Praecursor Update.bat`, `src/praecursor/analysis/accuracy_tracker.py`, `src/praecursor/consensus/engine.py`
- Database / Persistence: `signal_history.db` or SQLite database (`praecursor.db`), CSV archives

## Requirements Coverage Matrix

| Req | Feature Description | Tier 1 (Coverage) | Tier 2 (Boundaries) | Tier 3 (Combinations) | Tier 4 (Real Scenarios) |
|-----|--------------------|-------------------|---------------------|-----------------------|-------------------------|
| R1  | Autonomous 5 PM Scheduling | 5 tests | 5 tests | Pairwise with R2, R3 | 2 scenario tests |
| R2  | Intraday Target Verification | 5 tests | 5 tests | Pairwise with R4, R1 | 2 scenario tests |
| R3  | Cumulative Historical Archive | 5 tests | 5 tests | Pairwise with R1, R4 | 2 scenario tests |
| R4  | Data Source Consensus | 5 tests | 5 tests | Pairwise with R2, R3 | 2 scenario tests |

## Test Case Breakdown (49 Total)

### Tier 1: Feature Coverage (20 tests)
- `test_r1_scheduled_task_registration`: Verify PowerShell/Batch script registers Windows Scheduled Task for 5:00 PM.
- `test_r1_scheduled_task_non_interactive`: Verify task execution runs without manual intervention.
- `test_r1_scheduled_task_trigger_time`: Verify trigger is set precisely to 17:00 (5:00 PM) on trading days.
- `test_r1_scheduled_task_action_command`: Verify action command invokes python script/bat file correctly.
- `test_r1_scheduled_task_exit_code`: Verify scheduled task script returns exit code 0 on successful run.

- `test_r2_intraday_high_hits_target_close_lower`: Verify intraday high >= target % counts as HIT even if close < target.
- `test_r2_intraday_high_hits_exact_target`: Verify intraday high == target % counts as HIT.
- `test_r2_intraday_high_exceeds_target`: Verify intraday high > target % counts as HIT.
- `test_r2_intraday_high_below_target_close_below`: Verify intraday high < target % and close < target % counts as MISS.
- `test_r2_intraday_high_below_target_close_above`: Verify close above target with high below target percentage classification rules.

- `test_r3_cumulative_append`: Verify updater appends new daily records to history archive instead of overwriting.
- `test_r3_baseline_16_records`: Verify history archive starts/maintains baseline of 16 historical records.
- `test_r3_accuracy_percentage_calculation`: Verify running total accuracy percentage is correctly calculated over cumulative records.
- `test_r3_persistence_across_runs`: Verify history archive state persists across multiple scanner/updater invocations.
- `test_r3_record_fields`: Verify each archived record contains required fields (date, symbol, target_pct, intraday_high, close, hit_status).

- `test_r4_multi_source_fetch_logs`: Verify logs explicitly show fetching from TradingView and Mubasher.
- `test_r4_consensus_matching_sources`: Verify consensus engine resolves price when TradingView and Mubasher agree.
- `test_r4_consensus_outlier_rejection`: Verify consensus engine rejects anomalous data from one source when other agrees.
- `test_r4_consensus_log_comparison`: Verify explicit output logging comparing values from at least 2 data sources.
- `test_r4_source_fallback`: Verify system handles single-source availability gracefully.

### Tier 2: Boundary & Corner Cases (20 tests)
- `test_r1_reregister_existing_task`: Verify task scheduler registration handles existing task overwrites gracefully.
- `test_r1_missing_script_path`: Verify error handling when script path is missing or invalid.
- `test_r1_offline_network_execution`: Verify scheduled task handles offline network state without crashing.
- `test_r1_non_admin_permission_handling`: Verify scheduled task script provides informative error if elevated privileges are needed.
- `test_r1_custom_time_parameter`: Verify scheduling script accepts custom execution time parameters.

- `test_r2_floating_point_target_precision`: Verify target % comparison with floating point precision (e.g. 7.5000001% vs 7.5%).
- `test_r2_zero_atr_target`: Verify target verification handling when ATR or target calculation is 0 or undefined.
- `test_r2_circuit_breaker_high`: Verify target verification when intraday high reaches +20% limit up circuit breaker.
- `test_r2_zero_high_volume`: Verify handling of stock with 0 intraday volume or stagnant high.
- `test_r2_negative_or_nan_prices`: Verify graceful rejection of NaN or negative intraday high values.

- `test_r3_corrupted_archive_recovery`: Verify system recovers or reports clean error when history archive file is corrupted.
- `test_r3_large_archive_appends`: Verify performance and correctness when appending to an archive with 100+ records.
- `test_r3_duplicate_date_symbol_handling`: Verify handling of duplicate evaluation requests for same date and symbol.
- `test_r3_empty_archive_initialization`: Verify system initializes baseline structure when starting from empty state.
- `test_r3_concurrent_archive_access`: Verify file lock / sqlite lock handling during archive appends.

- `test_r4_total_source_disagreement`: Verify behavior when TradingView and Mubasher return completely conflicting values.
- `test_r4_tradingview_single_bar_anomaly`: Verify consensus engine detects TradingView 1-bar / missing bar anomaly.
- `test_r4_mubasher_http_error`: Verify behavior when Mubasher API returns HTTP 500 / timeout.
- `test_r4_extreme_price_variance`: Verify logging and flagging when price variance between sources exceeds threshold (>10%).
- `test_r4_partial_data_fields`: Verify handling when one data source is missing intraday high but has close price.

### Tier 3: Cross-Feature Combinations (4 tests)
- `test_comb_r1_r3_scheduled_append`: Verify 5 PM scheduled run updates accuracy tracking and appends to cumulative archive without overwriting.
- `test_comb_r2_r4_consensus_target_verification`: Verify data source consensus calculates verified intraday high, which feeds directly into target hit verification.
- `test_comb_r1_r2_scheduled_target_eval`: Verify scheduled 5 PM updater retrieves candidates and evaluates target % hit vs close.
- `test_comb_r3_r4_consensus_archive_logging`: Verify consensus price data logs and consensus results are recorded into cumulative history archive.

### Tier 4: Real-World Scenarios (5 tests)
- `test_scenario_multi_day_pipeline`: Full end-to-end multi-day pipeline execution (Scan -> 5 PM Updater -> Consensus -> Hit Check -> Archive Append -> Model Retrain).
- `test_scenario_weekly_trading_simulation`: Simulate 5 consecutive trading days with 16 baseline records, verifying cumulative total grows to 21 records.
- `test_scenario_tradingview_outage_resilience`: Simulate TradingView returning bad 1-bar data during daily 5 PM run; Mubasher supplies clean data, target hit evaluated, archive updated cleanly.
- `test_scenario_scheduled_task_lifecycle`: Test Windows scheduled task registration script execution, task query, trigger execution via schtasks, and log verification.
- `test_scenario_updater_rerun_idempotency`: Run 5 PM updater twice on same day; verify state integrity and no corrupted cumulative totals.

## Execution Requirements
- Test runner: `pytest`
- Path: `tests/e2e/`
- Command: `pytest tests/e2e -v`
