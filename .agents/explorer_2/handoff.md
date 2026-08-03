# Handoff Report: PriceConsensusEngine and Multi-Source Data Fetching (Requirement R4)

**Agent**: Explorer 2  
**Milestone**: M2 / R4 Data Source Consensus Investigation  
**Date**: 2026-08-03  

---

## 1. Observation

### 1.1 Existing Consensus Architecture (`src/praecursor/consensus/price_consensus.py`)
- **`SourcePrice` Dataclass (lines 7–15)**:
  ```python
  @dataclass(frozen=True)
  class SourcePrice:
      source_name: str
      symbol: str
      trade_date: date
      close: float
      volume: int | None = None
  ```
  *Observation*: `SourcePrice` currently holds `close` and `volume`, but lacks intraday `high` (and `open`/`low`).
- **`SourceAgreement` Dataclass (lines 18–25)**:
  ```python
  @dataclass(frozen=True)
  class SourceAgreement:
      source_name: str
      close: float
      difference_percent: float
      agrees: bool
  ```
  *Observation*: Tracks agreement for `close` price only.
- **`PriceConsensusResult` Dataclass (lines 28–41)**:
  ```python
  @dataclass(frozen=True)
  class PriceConsensusResult:
      symbol: str
      trade_date: date
      consensus_close: float
      source_count: int
      agreeing_source_count: int
      target_source_count: int
      tolerance_percent: float
      minimum_agreeing_sources: int
      accepted: bool
      agreements: list[SourceAgreement] = field(default_factory=list)
      warnings: list[str] = field(default_factory=list)
  ```
  *Observation*: Returns `consensus_close` only; `consensus_high` is not tracked.
- **`PriceConsensusEngine.calculate()` (lines 106–143)**:
  ```python
  consensus_close = float(median([price.close for price in relevant_prices]))
  agreements = [self._calculate_agreement(price, consensus_close) for price in relevant_prices]
  ```
  *Observation*: Calculates median for `close` prices only. No logging is emitted via standard Python `logging` module (`logger.info(...)`).

### 1.2 Data Collector Implementations (`src/praecursor/collectors/`)
- **`TradingViewSource` (`src/praecursor/collectors/tradingview_source.py`)**:
  - Uses `tvDatafeed.TvDatafeed().get_hist(symbol=tv_symbol, exchange='EGX', interval=Interval.in_daily, n_bars=n_bars)` (lines 66–71).
  - Returns `CollectionResult` containing `PriceBar(date, open, high, low, close, volume)`.
- **`MubasherSource` (`src/praecursor/collectors/mubasher_source.py`)**:
  - Scrapes HTML page from `https://english.mubasher.info/markets/EGX/stocks/{symbol}/` (lines 92–104).
  - Parses Open, High, Low, Close (Latest Update), and Volume (lines 119–166).
  - Returns 1 `PriceBar` for today's date in `CollectionResult`.
- **`YahooFinanceSource` (`src/praecursor/collectors/yahoo_finance_source.py`)**:
  - Queries `https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}` (lines 59–72).
  - Parses daily chart history into `PriceBar` objects.
- **`StockAnalysisSource` (`src/praecursor/collectors/stockanalysis_source.py`)**:
  - Scrapes `https://stockanalysis.com/quote/egx/{symbol}/history/` (lines 100–126).
  - Parses daily HTML table rows into `PriceBar` objects.
- **`OfficialEGXSource` (`src/praecursor/collectors/official_egx_source.py`)**:
  - Unimplemented placeholder raising `NotImplementedError` (lines 14–18).

### 1.3 Scanner Workflow Consensus Integration (`src/praecursor/workflows/scanner.py`)
- **Consensus Sources Initialization (lines 359–364)**:
  ```python
  if self.enable_consensus and self.consensus_data_sources is None:
      self.consensus_data_sources = [
          StockAnalysisSource(symbol_mapper=self.symbol_mapper),
          MubasherSource(),
          TradingViewSource(symbol_mapper=self.symbol_mapper),
      ]
  ```
- **`_build_source_prices()` (lines 632–656)**:
  ```python
  source_prices.append(
      SourcePrice(
          source_name=result.source_name,
          symbol=symbol,
          trade_date=trade_date,
          close=bar.close,
          volume=bar.volume,
      )
  )
  ```
  *Observation*: `_build_source_prices` strips out `bar.high` when constructing `SourcePrice` for consensus.

### 1.4 Cache Storage Issues (`src/praecursor/storage/price_cache.py`)
- **`PriceCache.override_close()` (lines 87–94)**:
  ```python
  def override_close(self, symbol: str, source: str, date_obj: date, new_close: float) -> None:
      with sqlite3.connect(self.database_path) as connection:
          connection.execute(
              "UPDATE source_prices SET close = ? WHERE symbol = ? AND source = ? AND date(date) = date(?)",
              (new_close, symbol, source, date_obj.isoformat())
          )
          connection.commit()
  ```
  *Observation*:
  1. SQL query references non-existent column `symbol` (actual table column name in `schema.py` line 29 is `ticker`).
  2. SQL query references non-existent expression `date(date)` (actual table column name is `trade_date`).
  3. `override_close` only updates `close`, not `high`.

### 1.5 Historical Accuracy Verification (`src/praecursor/analysis/accuracy_tracker.py`)
- **`AccuracyTracker.update_historical_outcomes()` (lines 76–97)**:
  - Queries `source_prices` table for `MAX(high) as high` and `close` where `ticker = ? AND trade_date > ?`.
  - Determines target hit via `high >= target` or solid gain `((high - latest_close) / latest_close) >= 0.025`.

---

## 2. Logic Chain

1. **Requirement R4 Goal**: Cross-reference multiple data sources (TradingView, Mubasher, etc.) for both **intraday high** and **close** prices, preventing false data from ruining accuracy tracking, with explicit logging of fetching and provider comparisons.
2. **Current System Deficit**:
   - `PriceConsensusEngine` only handles `close` prices; intraday `high` prices are omitted from `SourcePrice`, `SourceAgreement`, `PriceConsensusResult`, and `PriceConsensusEngine.calculate()`.
   - `ScannerWorkflow._build_source_prices()` discards `bar.high` when transferring collector bars to `SourcePrice`.
   - Standard python `logging` (`logger.info`) calls are missing in `PriceConsensusEngine.calculate()` and `ScannerWorkflow`, making it impossible to satisfy the requirement: *"The updater output logs explicitly show it fetching and comparing data from at least two sources (e.g. TradingView and Mubasher) before deciding on the high/close."*
   - SQLite cache override in `price_cache.py` has schema column mismatch bugs (`symbol` vs `ticker`, `date(date)` vs `trade_date`) and lacks high price consensus overriding.
3. **Synthesis**:
   To satisfy R4 and its Acceptance Criteria, the system needs:
   - Extended `SourcePrice` and `PriceConsensusResult` supporting both `high` and `close` consensus.
   - Dual consensus calculation in `PriceConsensusEngine` (median `close` and median `high`).
   - Explicit `logger.info()` logging during source fetching, per-provider extraction, pairwise difference calculation, and final consensus decision.
   - Integration in `ScannerWorkflow._build_source_prices()` to pass `bar.high`.
   - Corrected SQL statement in `PriceCache` to update both `high` and `close` consensus prices.

---

## 3. Caveats

- **Mubasher Date Scope**: Mubasher Info returns the *latest current quote* (1 bar for today's trading day), while TradingView, Yahoo Finance, and StockAnalysis return full historical daily series. When calculating consensus for today's or previous day's quote, Mubasher will match on `trade_date = date.today()`.
- **TradingView Anonymous Access**: `TradingViewSource` uses `tvDatafeed` in unauthenticated/anonymous mode. Network connection or rate limit failures should be caught gracefully and logged, falling back to other available providers (e.g. Yahoo Finance, StockAnalysis, Mubasher).
- **Minimum Agreeing Sources Parameter**: Default `minimum_agreeing_sources` in `PriceConsensusEngine` is set to 3, but `ScannerWorkflow` sets `minimum_agreeing_sources=2`. For 2-source evaluation (TradingView & Mubasher), `minimum_agreeing_sources` MUST be 2.

---

## 4. Conclusion & Recommendations for R4 Implementation

### 4.1 Recommended Design for `PriceConsensusEngine` (`src/praecursor/consensus/price_consensus.py`)

#### Dataclass Updates:
```python
@dataclass(frozen=True)
class SourcePrice:
    source_name: str
    symbol: str
    trade_date: date
    close: float
    high: float | None = None
    open: float | None = None
    low: float | None = None
    volume: int | None = None

@dataclass(frozen=True)
class SourceAgreement:
    source_name: str
    close: float
    high: float | None
    close_difference_percent: float
    high_difference_percent: float | None
    agrees_close: bool
    agrees_high: bool
    agrees: bool

@dataclass(frozen=True)
class PriceConsensusResult:
    symbol: str
    trade_date: date
    consensus_close: float
    consensus_high: float
    source_count: int
    agreeing_source_count: int
    target_source_count: int
    tolerance_percent: float
    minimum_agreeing_sources: int
    accepted: bool
    agreements: list[SourceAgreement] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
```

#### Consensus Logic Updates:
1. `consensus_close = float(median([p.close for p in prices if p.close > 0]))`
2. `valid_highs = [p.high for p in prices if p.high is not None and p.high > 0]`
3. `consensus_high = float(median(valid_highs)) if valid_highs else consensus_close`
4. Difference calculation:
   - `close_diff = abs(p.close - consensus_close) / consensus_close * 100`
   - `high_diff = abs(p.high - consensus_high) / consensus_high * 100` (if `p.high` present)
   - `agrees_close = close_diff <= tolerance_percent`
   - `agrees_high = high_diff <= tolerance_percent` (if `p.high` present)
   - `agrees = agrees_close and (agrees_high if p.high is not None else True)`

#### Explicit Logging Requirement:
Use `logger = logging.getLogger("praecursor.consensus")`:
```python
logger.info("Comparing multi-source price data for %s on %s across %d sources:", symbol, trade_date, len(relevant_prices))
for p in relevant_prices:
    logger.info("  [Source: %s] High: %s, Close: %.2f", p.source_name, f"{p.high:.2f}" if p.high else "N/A", p.close)
logger.info("Calculated Consensus for %s (%s): Consensus High = %.2f, Consensus Close = %.2f", symbol, trade_date, consensus_high, consensus_close)
for ag in agreements:
    logger.info("  Agreement [%s]: Close Diff = %.2f%% (Agrees: %s), High Diff = %s (Agrees: %s)",
                ag.source_name, ag.close_difference_percent, ag.agrees_close,
                f"{ag.high_difference_percent:.2f}%" if ag.high_difference_percent is not None else "N/A",
                ag.agrees_high)
```

### 4.2 Recommended Updates for `ScannerWorkflow` (`src/praecursor/workflows/scanner.py`)
1. In `_build_source_prices`:
   ```python
   source_prices.append(
       SourcePrice(
           source_name=result.source_name,
           symbol=symbol,
           trade_date=trade_date,
           close=bar.close,
           high=bar.high,
           volume=bar.volume,
       )
   )
   ```
2. Log explicit data source fetching:
   ```python
   logger.info("Fetching price data for %s from sources: %s", symbol, ", ".join(s.name for s in self.consensus_data_sources))
   ```

### 4.3 Recommended Updates for `PriceCache` (`src/praecursor/storage/price_cache.py`)
Fix method signature and SQL query:
```python
def override_consensus_prices(self, symbol: str, source: str, date_obj: date, new_high: float, new_close: float) -> None:
    with closing(self._connect()) as connection:
        connection.execute(
            """
            UPDATE source_prices
            SET high = ?, close = ?
            WHERE ticker = ? AND source = ? AND trade_date = ?
            """,
            (new_high, new_close, symbol, source, date_obj.isoformat())
        )
        connection.commit()
```

---

## 5. Verification Method

To verify the implementation of R4:

1. **Unit Test Execution**:
   Run: `python -m unittest discover tests`
   Existing tests in `tests/test_consensus.py` and `tests/test_scanner_workflow.py` must pass.
2. **New Consensus Verification Unit Test**:
   Create a test in `tests/test_consensus.py` that verifies:
   - Multi-source prices containing `high` and `close` from `tradingview` and `mubasher`.
   - `PriceConsensusEngine.calculate()` returns valid `consensus_high` and `consensus_close`.
   - Python logger produces explicit log messages showing both TradingView and Mubasher fetching and comparison.
3. **SQL Cache Check**:
   Inspect SQLite `source_prices` table in database using Python `sqlite3`:
   ```python
   import sqlite3
   conn = sqlite3.connect("data/scanner.db")
   rows = conn.execute("SELECT ticker, trade_date, source, high, close FROM source_prices").fetchall()
   ```
   Verify updated rows match consensus high and close.

---
