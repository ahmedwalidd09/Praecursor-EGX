# Scanner improvements and verification

Verified November 8, 2026. Repository: `C:\Users\moody\Documents\Codex\Praecursor-EGX`.

## Open the application

Double-click **Praecursor EGX** on the Windows desktop. The launcher starts the local server if needed and opens <http://127.0.0.1:8765>. The user confirmed that the shortcut opens the dashboard. The final server restart and health/overview requests passed. Search and stock details were checked in the browser earlier; the browser helper was unavailable for the final repeat.

Use **Run market scan** to refresh prices and saved signals. Use **Evaluate updated models** to rebuild revised research data and evaluate both horizons. Training can take considerable time. These dashboard actions do not broadcast Telegram messages. The saved HTML report uses the same page, with live controls hidden.

## What changed

| Audit area | Implemented behavior | Evidence |
|---|---|---|
| Price integrity | Complete canonical OHLCV candles; finite/positive checks; conflicting sources and unverified price jumps quarantined; raw observations preserved | `data/canonical.py`, `data/stock_builder.py`; canonical and outcome regression tests |
| Sessions and freshness | Cairo cutoff, Sunday–Thursday sessions, explicit closure overrides, completed-session validation; unfinished cache entries cannot be reused | `core/sessions.py`, `data/data_manager.py`; weekend/cache tests; live expected session matched November 5 |
| Outcome accuracy | Version 3 target-touch labels separate from executable trades; next-open entry, gaps, missing candles and ambiguous stop/target ordering explicit; 25 bps cost scenario | `analysis/outcomes.py`, `analysis/verified_history.py`; outcome and historical archive tests |
| Feature consistency | Shared 35-feature schema, repaired daily VPOC extraction/units, correct Thursday weekly grouping; missing measurements remain missing | `ml/features.py`, indicator regression tests |
| Market context | Date-aligned peer breadth and sector context; excludes the stock itself; no persistent global state; explicitly a scan-universe benchmark | `scoring/market_context.py`; order/date-isolation tests |
| Prediction consistency | A scan computes each prediction once; stored targets/stops exported unchanged; unsupported Kelly sizing removed; experimental forecasts excluded from live model loading | `workflows/scanner.py`, `scoring/next_day.py`, `scoring/swing.py`, dashboard export tests |
| Independent model evaluation | Date-separated training, tuning, calibration and test blocks; duplicate removal and label-maturity purging; calibrated probabilities and constant/technical baselines | `ml/validation.py`; split/maturity and immutable-manifest tests; both final validation reports |
| Model eligibility | Versioned immutable artifacts, fail-closed live loading, identical unseen-session incumbent comparison, atomic promotion; failed candidates remain inactive | `ml/prediction.py`, `ml/validation.py`; incompatible/future model tests; both real candidates rejected |
| Historical replay | Expanding past-only model fitting/calibration for both horizons; unknown future outcomes stay in candidate selection | `ml/walk_forward.py`; completed next-day and swing replay CSV/JSON reports |
| Dashboard and desktop | Search, horizon/filter controls, saved levels, data quality, truthful validation and missing probabilities; local action authorization; installed desktop launcher | API/authorization/host/export tests; live API checks; user-confirmed shortcut |

## Real-data results

The research snapshot contains **48,301 samples across 252 sessions**, reconstructed from 188,229 raw rows. It accepted 172,256 canonical candles and rejected 1,803 symbol/session groups. Feature and label versions are both 3. The final scan subsequently added three raw rows; the frozen research snapshot and its model reports retain their original identity. Subsequent model evaluation now detects same-session collection changes as well as new sessions.

The final scan saved **202 symbols**, with **33 errors** for unavailable, stale or suspect history. The live API returned feature version 3, price/expected session **2026-11-05**, `stale=false`, and zero next-day model probabilities. This is technical scoring, not a validated probability service.

| Frozen holdout | Next day | 20-session swing |
|---|---:|---:|
| Test sessions | 38 | 35 |
| Selected / resolved | 10 / 10 | 175 / 175 |
| Target touches among selections | 80.0% | 22.9% |
| Session coverage | 21.1% | 100% |
| Conservative mean net return per selection | +3.81% | −1.22% |
| Promotion | Rejected: fewer than 40 selections | Rejected: calibration and profitable baseline improvement failed |

The next-day percentage is based on only ten selections and is **not evidence of reliable 80% accuracy**. Neither candidate was activated. Test results were not used to retune and retry the same model version.

The separate expanding-window research replay selected 1,105 next-day signals over 221 sessions: 1,096 resolved, 9 unknown, 36.50% target-touch precision among resolved selections, and +0.69% mean modeled net return where available. Swing selected 935 over 187 sessions: 797 resolved, 138 unknown, 47.55% resolved precision and +0.92% mean available modeled net return. These are retrospective research diagnostics using a different rolling strategy, not results of the frozen holdout model or proof of live profitability. Missing outcomes are counted explicitly; return averages exclude unavailable returns.

## Verification

- `python -m pytest -q`: **144 passed, 10 skipped**. The skipped tests require real Windows scheduler registration and were deliberately not enabled.
- `python tools/walk_forward_backtest.py --horizon next_day`: completed.
- `python tools/walk_forward_backtest.py --horizon swing`: completed.
- `python tools/track_outcomes.py`: completed; 1,559 distinct resolved historical targets, 69 touches. Legacy missing stops remain unknown for trade-win statistics.
- `python tools/regenerate_dashboard.py`: completed using saved predictions.
- `GET /api/health` and `GET /api/overview`: passed after restarting the final backend.
- `git diff --check`: passed.

Detailed machine-readable evidence is in the delivery folder's `verification.json`; raw validation, replay and scan outputs remain under `reports/` and `logs/`.

## Limits that remain

Vendor history can be revised, and historical universe membership is not recoverable, so reconstructed results retain revision/survivorship bias. Prospective observations are needed to establish a live edge. A full authoritative holiday feed and corporate-action feed are not installed: verified closure dates and corporate-action factors require explicit input; suspect or stale data is withheld. A single valid candle source is allowed for research, while live confidence separately records source agreement. Returns use a fixed 25 bps round-trip scenario, not measured spreads, order-book fills, broker charges or market impact. The older generic forward-return backtest remains a technical diagnostic; the versioned replay and holdout reports are the model-validation evidence.

## Daily briefing update

The daily shortlist selects five eligible research candidates, with a soft two-per-sector preference. Missing second-source confirmation is displayed separately from ranking; conflicting or stale candles, insufficient history, illiquid symbols and locked limit-up closes remain excluded. Every selection records its rank and reasons in SQLite, CSV, the dashboard and Telegram. If fewer than five qualify, the briefing states the shortage instead of relaxing data checks.

GitHub Actions runs Saturday–Wednesday at 18:30 UTC (20:30 Cairo winter / 21:30 summer), using completed prices for the following session. Daily delivery skips expensive model retraining; model evaluation remains an explicit operation. Telegram requires encrypted repository secrets and a successful API response; previews and failures no longer claim delivery. Database release snapshots use SQLite backup, and workflow concurrency prevents overlapping writes.

Validation: 150 tests passed, 10 skipped. Live scan: 176 successful symbols and 59 exclusions, with five ranked candidates and saved reasons. This selection policy is a research shortlist, not a validated increase in trading win rate.


## Automatic feedback learning

A separate `model_learning.yml` workflow runs Sunday–Thursday at 19:30 UTC. It refreshes completed prices without publishing a new prediction, resolves saved targets, exports the original saved features, and trains challengers in a separate job. Database writes share the daily scanner concurrency lock; training releases that lock and uses a fixed exported snapshot. Thursday is included so Wednesday candidates are resolved before the weekend.

The live dataset keeps the first prediction per symbol/feature session, requires the current feature and label versions, and excludes predictions recorded on or after their target session date. Missing or conflicting outcomes remain unresolved, never artificial misses. Target touches and executable trade outcomes remain separate. All eligible saved predictions are available for training, rather than only the selected winners or five candidates.

Published-only training requires enough distinct sessions for the existing chronological train/tune/calibration/test split (at least 40 before further maturity and sample checks). Until then, it records insufficient evidence and preserves the incumbent or technical ranking. Legacy predictions with incompatible or missing features are not treated as equivalent training examples. Model state persists separately in the `models-latest` release and is restored by the next daily scan; rejected challengers never replace accepted models.
