from datetime import date, timedelta
from math import isnan

from praecursor.collectors.yahoo_finance_source import YahooFinanceSource
from praecursor.data.data_manager import DataManager
from praecursor.data.stock_builder import CachedStockBuilder
from praecursor.data.symbol_mapper import SymbolMapper
from praecursor.scoring.analyzer import Analyzer
from praecursor.scoring.ema import EMAIndicator
from praecursor.scoring.rsi import RSIIndicator
from praecursor.storage.price_cache import PriceCache


LOOKBACK_DAYS = 120
MINIMUM_BARS = 10
SOURCE_NAME = "yahoo_finance"
WARNING_PREVIEW_LIMIT = 5


def main() -> int:
    end_date = date.today()
    start_date = end_date - timedelta(days=LOOKBACK_DAYS)

    symbol_mapper = SymbolMapper.from_csv()
    symbols = symbol_mapper.get_yahoo_symbols()

    cache = PriceCache()
    data_manager = DataManager(
        sources=[YahooFinanceSource(symbol_mapper=symbol_mapper)],
        minimum_bars=MINIMUM_BARS,
        price_cache=cache,
    )
    stock_builder = CachedStockBuilder(
        price_cache=cache,
        symbol_mapper=symbol_mapper,
        source_name=SOURCE_NAME,
    )
    analyzer = create_analyzer()

    print("Updating and analyzing real EGX price data")
    print(f"Database: {cache.path}")
    print(f"Source: {SOURCE_NAME}")
    print(f"Configured symbols: {', '.join(symbols)}")
    print(f"Date range: {start_date} to {end_date}")
    print()

    analyzed_symbols = 0

    for symbol in symbols:
        try:
            update_result = data_manager.fetch_history(symbol, start_date, end_date)
            stock = stock_builder.build(symbol, start_date, end_date)
            indicator_results = analyzer.analyze(stock)
            cached_bars = cache.load(symbol, SOURCE_NAME, start_date, end_date)
            total_cached_rows = cache.count(symbol, SOURCE_NAME)

            analyzed_symbols += 1
            print_symbol_report(
                symbol=symbol,
                company=stock.company,
                downloaded_bars=len(update_result.price_bars),
                cached_bars=len(cached_bars),
                total_cached_rows=total_cached_rows,
                latest_close=stock.latest().close,
                latest_date=stock.latest().date.date(),
                indicator_results=indicator_results,
                warnings=update_result.warnings,
            )
        except Exception as error:
            print("=" * 40)
            print(symbol)
            print(f"ERROR: {error}")
            print()

    if analyzed_symbols == 0:
        return 1

    return 0


def create_analyzer() -> Analyzer:
    analyzer = Analyzer()
    analyzer.add_indicator(EMAIndicator(20))
    analyzer.add_indicator(RSIIndicator(14))
    return analyzer


def print_symbol_report(
    symbol: str,
    company: str,
    downloaded_bars: int,
    cached_bars: int,
    total_cached_rows: int,
    latest_close: float,
    latest_date: date,
    indicator_results: list,
    warnings: list[str],
) -> None:
    print("=" * 40)
    print(symbol)
    print(company)
    print(f"Downloaded bars: {downloaded_bars}")
    print(f"Cached bars in date range: {cached_bars}")
    print(f"Total cached rows for source: {total_cached_rows}")
    print(f"Latest Date: {latest_date}")
    print(f"Latest Close: {latest_close:.2f}")

    for result in indicator_results:
        print(f"{result.name}: {format_indicator_value(result.value)}")

    print_warnings(warnings)
    print()


def format_indicator_value(value: float) -> str:
    if isnan(value):
        return "N/A"

    return f"{value:.2f}"


def print_warnings(warnings: list[str]) -> None:
    print(f"Warnings: {len(warnings)}")

    for warning in warnings[:WARNING_PREVIEW_LIMIT]:
        print(f"  - {warning}")

    remaining_warning_count = len(warnings) - WARNING_PREVIEW_LIMIT

    if remaining_warning_count > 0:
        print(f"  ... {remaining_warning_count} more warnings")


if __name__ == "__main__":
    raise SystemExit(main())
