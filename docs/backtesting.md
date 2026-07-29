# Praecursor-EGX Backtesting

Praecursor-EGX includes an initial research backtester focused on model calibration.

## What it tests

The current backtester evaluates historical technical signals using cached Yahoo Finance price history.

It measures forward returns after configurable horizons, defaulting to:

```text
1 bar
2 bars
5 bars
10 bars
20 bars
```

The 1-bar and 2-bar horizons are included because the main scanner goal is to identify stocks that may move in the next trading session.

## What it does not test yet

This is not a full production backtester. It currently does not model:

```text
transaction costs
bid/ask spread
position sizing
stop losses
take profits
portfolio constraints
historical consensus availability
```

Historical consensus is not included because we did not collect multi-source consensus in the past for every historical date. The backtester therefore evaluates the technical signal model first.

## Run

To use currently cached data:

```powershell
python tools/run_backtest.py
```

To download/cache the requested range first, then backtest:

```powershell
python tools/run_backtest.py --prepare-cache
```

Optional:

```powershell
python tools/run_backtest.py --symbols SWDY,COMI
python tools/run_backtest.py --horizons 1 2 5 10 20 40
python tools/run_backtest.py --minimum-history-bars 260
python tools/run_backtest.py --minimum-signals-per-label 20
python tools/run_backtest.py --missed-move-threshold 5
```

## Reports

Backtest reports are written to:

```text
reports/backtest_signals.csv
reports/backtest_summary.csv
reports/backtest_symbol_summary.csv
reports/backtest_score_buckets.csv
reports/backtest_best_signals.csv
reports/backtest_worst_signals.csv
reports/backtest_label_examples.csv
reports/backtest_missed_movers.csv
reports/backtest_overextension.csv
reports/backtest_data_issues.csv
reports/backtest_summary.md
```

## Calibration features

The backtester now reports:

```text
summary by predictor label
summary by score bucket
summary by symbol
best/worst global signals
best/worst examples within each label
missed next-day movers
RSI-overextended follow-through samples
data issue flags
calibration notes
```

## Missed movers

A missed mover is currently defined as:

```text
label is Avoid Tomorrow or Watchlist Tomorrow
and 1-bar forward return >= missed_move_threshold
```

Default threshold:

```text
5%
```

## Data issue flags

The backtester can flag suspicious cached data:

```text
missing_data
stale_data
mostly_flat_prices
zero_volume
```

This helps identify symbols that should not be trusted in calibration.

## Interpreting results

Small sample sizes are not reliable. If a label has only a few historical signals, treat its result as anecdotal until more symbols and history are available.

A good calibration question is:

> Which label has the best 1-bar average return and 1-bar win rate?

If that is not the current strongest label, the next-day scoring rules need adjustment.
