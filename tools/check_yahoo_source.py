from datetime import date, timedelta

from praecursor.collectors.yahoo_finance_source import YahooFinanceSource
from praecursor.data.data_manager import DataManager
from praecursor.data.symbol_mapper import SymbolMapper


LOOKBACK_DAYS = 450
MINIMUM_BARS = 10


def main() -> int:
    end_date = date.today()
    start_date = end_date - timedelta(days=LOOKBACK_DAYS)

    symbol_mapper = SymbolMapper.from_csv()
    symbols = symbol_mapper.get_yahoo_symbols()

    manager = DataManager(
        sources=[YahooFinanceSource(symbol_mapper=symbol_mapper)],
        minimum_bars=MINIMUM_BARS,
    )

    print("Checking Yahoo Finance source")
    print(f"Configured symbols: {', '.join(symbols)}")
    print(f"Date range: {start_date} to {end_date}")
    print()

    successful_symbols = 0

    for symbol in symbols:
        try:
            result = manager.fetch_history(symbol, start_date, end_date)
            latest_bar = result.price_bars[-1]
            successful_symbols += 1

            print("=" * 40)
            print(symbol)
            print(f"Source: {result.source_name}")
            print(f"Bars: {len(result.price_bars)}")
            print(f"Latest date: {latest_bar.date.date()}")
            print(f"Latest close: {latest_bar.close:.2f}")
            print(f"Latest volume: {latest_bar.volume:,}")
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
