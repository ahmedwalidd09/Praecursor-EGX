# Praecursor-EGX

Praecursor-EGX is an open-source Python scanner for Egyptian Exchange (EGX) opportunities using public market data, technical indicators, multi-source consensus, and explainable scoring.

The project currently supports a one-command scanner workflow that:

1. downloads public EGX stock data,
2. validates and caches source data in SQLite,
3. calculates technical indicators,
4. checks latest-close consensus across sources,
5. ranks configured symbols,
6. stores signal history,
7. generates CSV and Markdown reports.

## Current data sources

| Source | Status | Role |
| --- | --- | --- |
| Yahoo Finance | Implemented | Primary long-history OHLCV source. |
| StockAnalysis | Implemented | Recent-history and latest-close consensus source. |
| Mubasher | Implemented latest quote | Delayed/latest quote source, cached separately. |
| Official EGX | Planned | Future authoritative validation source. |
| TradingView | Research required | Potential future confirmation source. |
| InvestingPro | Deferred | May require subscription/login. |

## Install

From the project root:

```powershell
pip install -e .
```

## Run the scanner

Recommended development command:

```powershell
python tools/run_scanner.py
```

After `pip install -e .`, installed command also works:

```powershell
praecursor-scan
```

This writes:

```text
reports/opportunity_ranking.csv
reports/opportunity_ranking.md
reports/archive/opportunity_ranking_YYYYMMDD_HHMMSS.csv
reports/archive/opportunity_ranking_YYYYMMDD_HHMMSS.md
```

It also stores scanner run history in:

```text
database/praecursor.db
```

## Configuration

Default scanner settings live in:

```text
config/scanner.json
```

Default symbol mappings live in:

```text
config/symbols.csv
```

You can override the config file:

```powershell
python tools/run_scanner.py --config config/scanner.json
```

## Useful scanner options

Scan only selected symbols:

```powershell
python tools/run_scanner.py --symbols COMI,SWDY
```

Change primary lookback window:

```powershell
python tools/run_scanner.py --lookback-days 600
```

Disable consensus checks:

```powershell
python tools/run_scanner.py --no-consensus
```

Disable saving signal history:

```powershell
python tools/run_scanner.py --no-history
```

Disable timestamped archive reports:

```powershell
python tools/run_scanner.py --no-archive-reports
```

Show recent stored scanner runs:

```powershell
python tools/show_signal_history.py
```

Show only the latest two runs:

```powershell
python tools/show_signal_history.py --limit 2
```

List archived reports:

```powershell
python tools/list_reports.py
```

Run initial historical signal backtest:

```powershell
python tools/run_backtest.py
```

Backtest selected symbols:

```powershell
python tools/run_backtest.py --symbols SWDY,COMI
```

List source registry:

```powershell
python tools/list_data_sources.py
```

Installed command equivalents:

```powershell
praecursor-history
praecursor-reports
praecursor-sources
```

## Run tests

```powershell
python tools/run_tests.py
```

The test suite uses Python's built-in `unittest` module and does not require external test dependencies.

## Current indicators

The scanner currently reports:

```text
EMA20
EMA50
EMA200
RSI14
MACD
MACDSignal
MACDHistogram
Momentum20
TrendStrength
AvgVolume20
RelVolume20
ATR14
ATRPercent14
Breakout20
Breakout50
CloseHigh250
NearCloseHigh250Percent
VolumeConfirmedBreakout
```

## Current predictor labels

The scanner produces a final predictor label:

```text
Strong Candidate
Extended Breakout
Watchlist
Low Confidence
Low Data Quality
Avoid
```

See:

```text
docs/scoring.md
docs/prediction_labels.md
docs/data_sources.md
```

## Important disclaimer

Praecursor-EGX is a research and decision-support tool. It is not financial advice and does not guarantee future returns.
