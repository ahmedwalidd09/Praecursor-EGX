# E2E Test Infra: Praecursor-EGX

## Test Philosophy
- Opaque-box, requirement-driven E2E testing based on user specifications in `ORIGINAL_REQUEST.md`.
- No internal code modification inside tests — tests exercise system entry points, CLI workflows, API boundaries, and persistent database/CSV outputs.
- Test design methodology: 4-tier approach (Tier 1 Feature Coverage, Tier 2 Boundary & Corner Cases, Tier 3 Cross-Feature Combinations, Tier 4 Real-World Application Scenarios).

## Feature Inventory
| # | Feature Requirement | Source | Tier 1 Count | Tier 2 Count | Tier 3 | Tier 4 |
|---|--------------------|--------|:------------:|:------------:|:------:|:------:|
| 1 | R1: Autonomous 5 PM Scheduling | ORIGINAL_REQUEST §R1 | 5 | 5 | ✓ | 2 |
| 2 | R2: Intraday Target Verification | ORIGINAL_REQUEST §R2 | 5 | 5 | ✓ | 2 |
| 3 | R3: Cumulative Historical Archive | ORIGINAL_REQUEST §R3 | 5 | 5 | ✓ | 2 |
| 4 | R4: Data Source Consensus | ORIGINAL_REQUEST §R4 | 5 | 5 | ✓ | 2 |
| **Total** | | | **20** | **20** | **4** | **5** |

## Test Architecture
- **Test Runner**: `pytest`
- **Location**: `tests/e2e/`
- **Modules**:
  - `tests/e2e/conftest.py`: Fixtures for temporary SQLite databases, mock market data sources, scheduled task runners, and baseline historical records (16 baseline entries).
  - `tests/e2e/test_r1_scheduling.py`: Tier 1 & Tier 2 tests for Windows Task Scheduler registration, trigger timing (17:00), non-interactive execution, exit codes, re-registration, offline fallback.
  - `tests/e2e/test_r2_target_verification.py`: Tier 1 & Tier 2 tests for intraday high target verification (high >= target = HIT regardless of close), floating point target precision, zero ATR, limit-up circuit breaker, NaN prices.
  - `tests/e2e/test_r3_historical_archive.py`: Tier 1 & Tier 2 tests for cumulative historical database archiving, 16 baseline record preservation, append-only logic, accuracy percentage calculations, corrupt DB recovery, large archives.
  - `tests/e2e/test_r4_data_consensus.py`: Tier 1 & Tier 2 tests for multi-source consensus (TradingView & Mubasher), explicit logging of fetched/compared prices for intraday highs and closes, outlier rejection, single source fallback.
  - `tests/e2e/test_tier3_combinations.py`: Cross-feature integration tests (R1+R3, R2+R4, R1+R2, R3+R4).
  - `tests/e2e/test_tier4_scenarios.py`: Realistic end-to-end multi-day pipeline execution, 5-day simulated trading week, TradingView outage resilience, schtasks lifecycle, rerun idempotency.

## Real-World Application Scenarios (Tier 4)
| # | Scenario Name | Features Exercised | Expected Outcome |
|---|---------------|--------------------|------------------|
| 1 | `test_scenario_multi_day_pipeline` | R1, R2, R3, R4 | Full automated pipeline run processes daily scan, consensus fetch, target hit check, archive append, model retrain. |
| 2 | `test_scenario_weekly_trading_simulation` | R1, R2, R3 | 5 simulated trading days grow 16 baseline records to 21 cumulative records without overwriting. |
| 3 | `test_scenario_tradingview_outage_resilience` | R2, R3, R4 | Mubasher supplies clean prices when TradingView returns 1-bar bad data; target hit is correctly evaluated and archived. |
| 4 | `test_scenario_scheduled_task_lifecycle` | R1, R3 | Task scheduler script registers task, schtasks triggers execution, logs confirm non-interactive completion. |
| 5 | `test_scenario_updater_rerun_idempotency` | R2, R3 | Re-running 5 PM updater on same day preserves archive integrity without duplicating records. |

## Coverage Thresholds
- Tier 1: ≥5 test cases per feature (20 total)
- Tier 2: ≥5 boundary/corner cases per feature (20 total)
- Tier 3: 4 pairwise feature interaction test cases
- Tier 4: 5 realistic application-level scenario test cases
- **Total Minimum: 49 Test Cases**
