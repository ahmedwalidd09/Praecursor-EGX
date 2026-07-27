from datetime import date, timedelta
from math import isnan

from praecursor.data.stock_builder import CachedStockBuilder
from praecursor.data.symbol_mapper import SymbolMapper
from praecursor.scoring.analyzer import Analyzer
from praecursor.scoring.average_volume import AverageVolumeIndicator
from praecursor.scoring.ema import EMAIndicator
from praecursor.scoring.macd import MACDHistogramIndicator, MACDLineIndicator, MACDSignalIndicator
from praecursor.scoring.price_momentum import PriceMomentumIndicator
from praecursor.scoring.rsi import RSIIndicator
from praecursor.scoring.relative_volume import RelativeVolumeIndicator
from praecursor.scoring.trend_strength import TrendStrengthIndicator
from praecursor.storage.price_cache import PriceCache


LOOKBACK_DAYS = 450
SOURCE_NAME = "yahoo_finance"


def main() -> int:
    end_date = date.today()
    start_date = end_date - timedelta(days=LOOKBACK_DAYS)

    symbol_mapper = SymbolMapper.from_csv()
    symbols = symbol_mapper.get_yahoo_symbols()

    cache = PriceCache()
    stock_builder = CachedStockBuilder(
        price_cache=cache,
        symbol_mapper=symbol_mapper,
        source_name=SOURCE_NAME,
    )

    analyzer = Analyzer()
    analyzer.add_indicator(EMAIndicator(20))
    analyzer.add_indicator(EMAIndicator(50))
    analyzer.add_indicator(EMAIndicator(200))
    analyzer.add_indicator(RSIIndicator(14))
    analyzer.add_indicator(AverageVolumeIndicator(20))
    analyzer.add_indicator(RelativeVolumeIndicator(20))
    analyzer.add_indicator(MACDLineIndicator())
    analyzer.add_indicator(MACDSignalIndicator())
    analyzer.add_indicator(MACDHistogramIndicator())
    analyzer.add_indicator(PriceMomentumIndicator(20))
    analyzer.add_indicator(TrendStrengthIndicator())

    print("Analyzing cached real price data")
    print(f"Database: {cache.path}")
    print(f"Source: {SOURCE_NAME}")
    print(f"Configured symbols: {', '.join(symbols)}")
    print(f"Date range: {start_date} to {end_date}")
    print()

    analyzed_symbols = 0

    for symbol in symbols:
        try:
            stock = stock_builder.build(symbol, start_date, end_date)
            analyzed_symbols += 1
            latest_bar = stock.latest()
            indicator_results = analyzer.analyze(stock)

            print("=" * 40)
            print(stock.symbol)
            print(stock.company)
            print(f"Bars: {len(stock.history)}")
            print(f"Latest Date: {latest_bar.date.date()}")
            print(f"Latest Close: {latest_bar.close:.2f}")

            for result in indicator_results:
                formatted_value = "N/A" if isnan(result.value) else f"{result.value:.2f}"
                print(f"{result.name}: {formatted_value}")

            print()
        except Exception as error:
            print("=" * 40)
            print(symbol)
            print(f"ERROR: {error}")
            print("Tip: run 'python tools/check_price_cache.py' first to populate the cache.")
            print()

    if analyzed_symbols == 0:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
