from datetime import date, timedelta

from praecursor.collectors.yahoo_finance_source import YahooFinanceSource
from praecursor.data.data_manager import DataManager
from praecursor.data.symbol_mapper import SymbolMapper
from praecursor.storage.price_cache import PriceCache


LOOKBACK_DAYS = 120
MINIMUM_BARS = 10
SOURCE_NAME = "yahoo_finance"


def main() -> int:
    end_date = date.today()
    start_date = end_date - timedelta(days=LOOKBACK_DAYS)

    symbol_mapper = SymbolMapper.from_csv()
    symbols = symbol_mapper.get_yahoo_symbols()

    cache = PriceCache()
    manager = DataManager(
        sources=[YahooFinanceSource(symbol_mapper=symbol_mapper)],
        minimum_bars=MINIMUM_BARS,
        price_cache=cache,
    )

    print("Checking SQLite price cache")
    print(f"Database: {cache.path}")
    print(f"Configured symbols: {', '.join(symbols)}")
    print(f"Date range: {start_date} to {end_date}")
    print()

    successful_symbols = 0

    for symbol in symbols:
        try:
            result = manager.fetch_history(symbol, start_date, end_date)
            cached_bars = cache.load(symbol, SOURCE_NAME, start_date, end_date)
            total_cached_rows = cache.count(symbol, SOURCE_NAME)
            successful_symbols += 1

            print("=" * 40)
            print(symbol)
            print(f"Downloaded bars: {len(result.price_bars)}")
            print(f"Cached bars in date range: {len(cached_bars)}")
            print(f"Total cached rows for source: {total_cached_rows}")

            if cached_bars:
                latest_cached_bar = cached_bars[-1]
                print(f"Latest cached date: {latest_cached_bar.date.date()}")
                print(f"Latest cached close: {latest_cached_bar.close:.2f}")

            print(f"Warnings: {len(result.warnings)}")
            for warning in result.warnings[:5]:
                print(f"  - {warning}")

            if len(result.warnings) > 5:
                print(f"  ... {len(result.warnings) - 5} more warnings")

            print()
        except Exception as error:
            print("=" * 40)
            print(symbol)
            print(f"ERROR: {error}")
            print()

    if successful_symbols == 0:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
