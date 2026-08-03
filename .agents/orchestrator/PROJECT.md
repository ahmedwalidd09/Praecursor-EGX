# Project: Praecursor-EGX Autonomous Updater & Multi-Source Target Verifier

## Architecture
Praecursor-EGX is a Python-based stock market daily updater and scanner for EGX (Egyptian Exchange).
The pipeline supports:
1. Scheduled autonomous execution at 5 PM on trading days (via Windows Task Scheduler).
2. Data consensus using `PriceConsensusEngine` fetching from TradingView, Mubasher, etc.
3. Intraday target verification (evaluating high price vs target % return even if close is lower).
4. Cumulative historical archiving appending daily hits/misses, retaining 16 baseline accuracy records.

## Code Layout
- `src/`: Core Python packages (updaters, consensus engines, historical verifiers, scanners)
- `tools/` or `scripts/`: Registration scripts for Windows Task Scheduler (`register_task.ps1`, `Daily Praecursor Update.bat`)
- `tests/`: Unit and integration test suite (`tests/`, `tests/e2e/`)
- `database/` / `data/`: Signal history and historical archives (`database/praecursor.db`, `reports/archive/accuracy_history_archive.csv`)

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Intraday Target Verification & Historical Archiving | Verify intraday high target hits; persistent cumulative append archive with 16-record baseline | None | DONE |
| M2 | Multi-Source Consensus Integration | Integrate/extend PriceConsensusEngine to fetch/compare from TradingView & Mubasher | M1 | DONE |
| M3 | Autonomous 5 PM Scheduling & CLI Pipeline | Windows Task Scheduler registration (.ps1/.bat) executing update & scan | M1, M2 | DONE |
| M4 | E2E Testing & Hardening | Opaque-box E2E test suite validation & Tier 5 adversarial coverage hardening | M1, M2, M3 | DONE |

## Interface Contracts
### PriceConsensusEngine
- Interface for querying multiple data providers (TradingView, Mubasher, etc.)
- Returns consensus intraday high and close prices with log outputs detailing source comparisons.

### Accuracy Tracker & History Archive
- Function to update signal history with daily target checks.
- Logic: `intraday_high >= entry_price * (1 + target_pct)` -> HIT.
- Append to persistent archive (`praecursor.db` / `accuracy_history_archive.csv`) keeping running accuracy total.
