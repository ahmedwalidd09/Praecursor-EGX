# Praecursor-EGX Backtesting

Praecursor-EGX includes an initial research backtester.

## What it tests

The current backtester evaluates historical technical signals using cached Yahoo Finance price history.

It measures forward returns after configurable horizons, currently defaulting to:

```text
5 bars
10 bars
20 bars
```

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
python tools/run_backtest.py --horizons 5 10 20 40
python tools/run_backtest.py --minimum-history-bars 260
python tools/run_backtest.py --minimum-signals-per-label 20
```

## Reports

Backtest reports are written to:

```text
reports/backtest_signals.csv
reports/backtest_summary.csv
reports/backtest_symbol_summary.csv
reports/backtest_best_signals.csv
reports/backtest_worst_signals.csv
reports/backtest_summary.md
```

## Interpreting results

The summary groups signals by historical label:

```text
Strong Candidate
Extended Breakout
Watchlist
Avoid
```

For each label, it reports:

```text
signal count
average forward return
win rate
sample-size warning
```

This helps answer:

> When the model produced a label historically, what happened after 5, 10, or 20 bars?

## Important calibration note

Small sample sizes are not reliable. If a label has only a few historical signals, treat its result as anecdotal until more symbols and history are available.
