from datetime import date, timedelta

from praecursor.collectors.collection_result import CollectionResult
from praecursor.collectors.stockanalysis_source import StockAnalysisSource
from praecursor.collectors.yahoo_finance_source import YahooFinanceSource
from praecursor.consensus.price_consensus import PriceConsensusEngine, SourcePrice
from praecursor.core.price_bar import PriceBar
from praecursor.data.data_manager import DataManager
from praecursor.data.symbol_mapper import SymbolMapper


LOOKBACK_DAYS = 180
MINIMUM_BARS = 10
TOLERANCE_PERCENT = 0.5
MINIMUM_AGREEING_SOURCES = 2
TARGET_SOURCE_COUNT = 5


def main() -> int:
    end_date = date.today()
    start_date = end_date - timedelta(days=LOOKBACK_DAYS)

    symbol_mapper = SymbolMapper.from_csv()
    symbols = symbol_mapper.get_stockanalysis_symbols()

    yahoo_manager = DataManager(
        sources=[YahooFinanceSource(symbol_mapper=symbol_mapper)],
        minimum_bars=MINIMUM_BARS,
    )
    stockanalysis_manager = DataManager(
        sources=[StockAnalysisSource(symbol_mapper=symbol_mapper)],
        minimum_bars=MINIMUM_BARS,
    )
    consensus_engine = PriceConsensusEngine(
        tolerance_percent=TOLERANCE_PERCENT,
        minimum_agreeing_sources=MINIMUM_AGREEING_SOURCES,
        target_source_count=TARGET_SOURCE_COUNT,
    )

    print("Checking real multi-source price consensus")
    print(f"Sources: yahoo_finance, stockanalysis")
    print(f"Configured symbols: {', '.join(symbols)}")
    print(f"Date range: {start_date} to {end_date}")
    print(f"Tolerance: {TOLERANCE_PERCENT:.2f}%")
    print(f"Acceptance rule for now: {MINIMUM_AGREEING_SOURCES} agreeing sources")
    print(f"Long-term target: 3 of {TARGET_SOURCE_COUNT} sources")
    print()

    successful_symbols = 0

    for symbol in symbols:
        try:
            yahoo_result = yahoo_manager.fetch_history(symbol, start_date, end_date)
            stockanalysis_result = stockanalysis_manager.fetch_history(symbol, start_date, end_date)
            common_date = find_latest_common_date(yahoo_result, stockanalysis_result)

            if common_date is None:
                raise ValueError("No common trade date found between Yahoo and StockAnalysis.")

            source_prices = build_source_prices(
                symbol,
                common_date,
                [yahoo_result, stockanalysis_result],
            )
            consensus_result = consensus_engine.calculate(symbol, common_date, source_prices)
            successful_symbols += 1

            print("=" * 40)
            print(symbol)
            print(f"Common date: {common_date}")
            print(f"Consensus close: {consensus_result.consensus_close:.2f}")
            print(
                f"Agreeing sources: "
                f"{consensus_result.agreeing_source_count}/{consensus_result.source_count}"
            )
            print(f"Agreement: {consensus_result.agreement_percent:.0f}%")
            print(f"Confidence vs 5-source target: {consensus_result.confidence_percent:.0f}%")
            print(f"Accepted with current 2-source rule: {consensus_result.accepted}")
            print("Source comparison:")

            for agreement in consensus_result.agreements:
                status = "AGREE" if agreement.agrees else "DISAGREE"
                print(
                    f"  - {agreement.source_name}: "
                    f"close={agreement.close:.2f}, "
                    f"difference={agreement.difference_percent:.2f}%, "
                    f"{status}"
                )

            warning_count = len(yahoo_result.warnings) + len(stockanalysis_result.warnings)
            print(f"Source warnings: {warning_count}")

            if consensus_result.warnings:
                print("Consensus warnings:")
                for warning in consensus_result.warnings:
                    print(f"  - {warning}")

            print()
        except Exception as error:
            print("=" * 40)
            print(symbol)
            print(f"ERROR: {error}")
            print()

    if successful_symbols == 0:
        return 1

    return 0


def find_latest_common_date(*results: CollectionResult) -> date | None:
    if not results:
        return None

    date_sets = [
        {bar.date.date() for bar in result.price_bars}
        for result in results
    ]
    common_dates = set.intersection(*date_sets)

    if not common_dates:
        return None

    return max(common_dates)


def build_source_prices(
    symbol: str,
    trade_date: date,
    results: list[CollectionResult],
) -> list[SourcePrice]:
    source_prices: list[SourcePrice] = []

    for result in results:
        bar = find_bar_for_date(result.price_bars, trade_date)

        if bar is None:
            continue

        source_prices.append(
            SourcePrice(
                source_name=result.source_name,
                symbol=symbol,
                trade_date=trade_date,
                close=bar.close,
                volume=bar.volume,
            )
        )

    return source_prices


def find_bar_for_date(price_bars: list[PriceBar], trade_date: date) -> PriceBar | None:
    for bar in price_bars:
        if bar.date.date() == trade_date:
            return bar

    return None


if __name__ == "__main__":
    raise SystemExit(main())
