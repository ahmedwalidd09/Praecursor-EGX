# Praecursor-EGX Data Sources

Praecursor-EGX is designed to use multiple public sources instead of trusting a single website.

## Current source roles

| Source | Status | Role |
| --- | --- | --- |
| Yahoo Finance | Implemented | Primary long-history source for indicators such as EMA20, EMA50, EMA200, RSI14, MACD, momentum, and volume. |
| StockAnalysis | Implemented | Recent-history and latest-close confirmation source. |
| Mubasher Info | Implemented latest quote | Delayed/latest quote cross-check source. It may be intraday and may not always match EOD dates. |
| Official EGX | Planned | Authoritative validation source. Implementation needs careful handling of the official website structure. |
| TradingView | Research required | Potential extra quote/signal confirmation source, subject to usage constraints. |
| InvestingPro | Deferred | May require subscription/login; not used for unauthenticated open-source scraping. |

## Current scanner source usage

The scanner currently uses:

- Yahoo Finance as the primary long-history source.
- StockAnalysis as the main latest-close consensus source.
- Mubasher as an optional delayed/latest quote consensus source.

Mubasher data may be current intraday quote data. If its quote date does not match the latest end-of-day date used by Yahoo/StockAnalysis, it is cached but not included in the close consensus for that EOD date.

## Consensus policy

Long-term target:

- collect 5 sources where feasible
- accept high-confidence values when at least 3 of 5 sources agree
- keep raw source data separate in SQLite
- produce consensus metadata in reports

Current live scanner policy:

- 2 agreeing sources: accepted but medium confidence
- 3+ agreeing sources: high confidence

## Confidence labels

- `low`: consensus rejected or insufficient agreement
- `medium`: two sources agree; useful but not final high confidence
- `high`: at least three sources agree against the five-source target

## Data quality labels

Data quality is currently based on warning rate:

- `high`: score >= 80
- `medium`: score >= 60
- `low`: score < 60

High warning counts usually indicate source rows where high/low values had to be normalized. EMA, RSI, MACD, momentum, and close-based breakouts rely mostly on close prices. ATR and future candlestick indicators should depend more heavily on high-quality high/low data.
