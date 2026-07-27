# Praecursor-EGX Data Sources

Praecursor-EGX is designed to use multiple public sources instead of trusting a single website.

## Current source roles

| Source | Status | Role |
| --- | --- | --- |
| Yahoo Finance | Implemented | Primary long-history source for indicators such as EMA20, EMA50, EMA200, RSI14. |
| StockAnalysis | Implemented | Recent-history and latest-close confirmation source. |
| Official EGX | Planned | Authoritative validation source. Implementation needs careful handling of the official website structure. |
| Mubasher Info | Planned | Regional delayed quote validation source. |
| TradingView | Research required | Potential extra quote/signal confirmation source, subject to usage constraints. |
| InvestingPro | Deferred | May require subscription/login; not used for unauthenticated open-source scraping. |

## Consensus policy

Current live scanner uses two real sources:

- Yahoo Finance
- StockAnalysis

A latest close is accepted when both current sources agree within the configured tolerance.

Long-term target:

- collect 5 sources where feasible
- accept high-confidence values when at least 3 of 5 sources agree
- keep raw source data separate in SQLite
- produce consensus metadata in reports

## Confidence labels

- `low`: consensus rejected or insufficient agreement
- `medium`: two sources agree; useful but not final high confidence
- `high`: at least three sources agree against the five-source target

## Data quality labels

Data quality is currently based on warning rate:

- `high`: score >= 80
- `medium`: score >= 60
- `low`: score < 60

High warning counts usually indicate source rows where high/low values had to be normalized. EMA and RSI rely on close prices, but future ATR/breakout indicators should depend more heavily on high-quality high/low data.
