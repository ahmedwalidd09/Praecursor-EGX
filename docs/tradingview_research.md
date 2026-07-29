# TradingView Source Research

TradingView is useful as a charting reference, but it is not currently integrated as an automated Praecursor-EGX data source.

## Current conclusion

Praecursor-EGX should not scrape TradingView chart internals or private browser API calls.

Reasons:

- TradingView does not provide a simple official public REST API for automated historical OHLCV access in the same way a market-data vendor does.
- Unofficial methods can be fragile and can break when TradingView changes its web app.
- Some third-party products market themselves as TradingView-compatible APIs, but they require separate signup/API keys and are not the same as scraping TradingView directly.

## Safe integration path

Only integrate TradingView-style data if one of these is available:

1. A documented, licensed TradingView-compatible API provider.
2. A user-provided API key for a legal third-party TradingView data API.
3. Manual exported CSV files from TradingView.

## Current project decision

TradingView remains marked as:

```text
research_required
```

It is not used by the scanner today.

Current production sources remain:

```text
Yahoo Finance
StockAnalysis
Mubasher latest quote
```
