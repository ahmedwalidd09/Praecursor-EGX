# Project: Praecursor-EGX HTML Generation & Pipeline Stability Audit

## Architecture
Praecursor-EGX is a Python-based stock market daily scanner and accuracy tracker for EGX (Egyptian Exchange).
The current phase focuses on:
1. HTML Dashboard Generation Audit (`src/praecursor/reporting/dashboard.py` and `src/praecursor/cli/dashboard.py`).
2. Pipeline Execution Stability (`tools/regenerate_dashboard.py` and `tools/run_autonomous_pipeline.py`).
3. Output HTML Verification (`reports/dashboard.html` malformed tag / structural checks).

## Code Layout
- `src/praecursor/reporting/dashboard.py`: Core dashboard HTML rendering logic.
- `src/praecursor/cli/dashboard.py`: CLI wrapper for dashboard generation.
- `src/praecursor/cli/scanner.py`: Scanner CLI interface parsing `--date` and workflow options.
- `src/praecursor/cli/telegram.py`: Telegram reporting CLI interface.
- `tools/regenerate_dashboard.py`: Script to regenerate `reports/dashboard.html`.
- `tools/run_autonomous_pipeline.py`: Script running the full daily autonomous pipeline.
- `tools/retrain_models.py`: Model retraining tool.
- `tests/test_dashboard_report.py`: Tests for HTML dashboard generation.
- `reports/dashboard.html`: Generated HTML dashboard report.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | HTML Generation Audit & Fixes | Remove extra `</div>` tag on line 79, add HTML escaping & null safety in `dashboard.py`, fix `cli/dashboard.py` doctype | M1 | R1 |
| 2 | Regenerate Dashboard Stability | Wrap `regenerate_dashboard.py` in `try...except`, handle empty DB with fallback, return exit code 0 | M2 | R2 / Criteria 1 |
| 3 | Autonomous Pipeline Stability | Add `--date` to `cli/scanner.py`, harden `retrain_models.py` & `telegram.py` empty DB handling, return exit code 0 | M2 | R2 / Criteria 2 |
| 4 | HTML Well-Formedness Verification | Add `StrictHTMLValidator` (`html.parser.HTMLParser`) to `tests/test_dashboard_report.py` ensuring zero tag errors | M3 | Criteria 3 |
| 5 | E2E & Forensic Audit | Review, challenge, and audit all implementation changes for correctness and low credit usage | M3 | Criteria 4 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | HTML Generation Logic Fixes | Audit & fix `src/praecursor/reporting/dashboard.py` and `src/praecursor/cli/dashboard.py` | None | DONE |
| M2 | Pipeline Execution Stability | Fix stability & runtime issues in `tools/regenerate_dashboard.py`, `tools/run_autonomous_pipeline.py`, `src/praecursor/cli/scanner.py`, `src/praecursor/cli/telegram.py`, and `tools/retrain_models.py` | M1 | DONE |
| M3 | E2E Verification & Forensic Audit | Run end-to-end verification, HTML validation, reviewer & challenger checks, and forensic audit | M1, M2 | IN_PROGRESS |

## Interface Contracts
### Dashboard HTML Generation (`src/praecursor/reporting/dashboard.py`, `src/praecursor/cli/dashboard.py`)
- Takes pipeline scan results and historical evaluation data.
- Generates `reports/dashboard.html`.
- Must output clean, valid HTML5 with matching start and end tags.
- Maintains black background, neon blue accents, red/green hit/miss styling.

### Pipeline Execution (`tools/regenerate_dashboard.py`, `tools/run_autonomous_pipeline.py`, `src/praecursor/cli/scanner.py`)
- Accepts optional `--date YYYY-MM-DD` parameter in `cli/scanner.py` and `run_autonomous_pipeline.py`.
- Executes data fetching, scoring, archive updating, and HTML dashboard rendering.
- Exits cleanly with status code 0 on valid inputs or empty historical database.
