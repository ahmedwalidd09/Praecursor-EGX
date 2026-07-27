from datetime import date, timedelta
from math import isnan

from praecursor.data.stock_builder import CachedStockBuilder
from praecursor.data.symbol_mapper import SymbolMapper
from praecursor.reporting.csv_report import OpportunityRankingCSVWriter
from praecursor.scoring.opportunity_score import OpportunityScore, OpportunityScorer
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
    scorer = OpportunityScorer()
    report_writer = OpportunityRankingCSVWriter()

    print("Ranking cached EGX opportunities")
    print(f"Database: {cache.path}")
    print(f"Source: {SOURCE_NAME}")
    print(f"Configured symbols: {', '.join(symbols)}")
    print(f"Date range: {start_date} to {end_date}")
    print()

    scores: list[OpportunityScore] = []

    for symbol in symbols:
        try:
            stock = stock_builder.build(symbol, start_date, end_date)
            scores.append(scorer.score(stock))
        except Exception as error:
            print("=" * 40)
            print(symbol)
            print(f"ERROR: {error}")
            print("Tip: run 'python tools/update_and_analyze.py' first to populate the cache.")
            print()

    if not scores:
        return 1

    ranked_scores = sorted(scores, key=lambda score: score.total_score, reverse=True)
    print_ranked_scores(ranked_scores)

    report_path = report_writer.write(ranked_scores)
    print(f"CSV report saved to: {report_path}")

    return 0


def print_ranked_scores(scores: list[OpportunityScore]) -> None:
    print("Opportunity ranking")
    print()

    for rank, score in enumerate(scores, start=1):
        print("=" * 40)
        print(f"#{rank} {score.symbol}")
        print(score.company)
        print(f"Score: {score.total_score:.0f}/{score.max_score:.0f} ({score.score_percent:.0f}%)")
        print(f"Latest Close: {score.latest_close:.2f}")
        print_indicator_values(score)
        print("Components:")

        for component in score.components:
            print(
                f"  - {component.name}: "
                f"{component.score:.0f}/{component.max_score:.0f} - {component.reason}"
            )

        print()


def print_indicator_values(score: OpportunityScore) -> None:
    indicator_names = ["EMA20", "EMA50", "EMA200", "RSI14", "AvgVolume20", "RelVolume20"]

    for indicator_name in indicator_names:
        value = score.indicator_values.get(indicator_name, float("nan"))
        print(f"{indicator_name}: {format_value(value)}")


def format_value(value: float) -> str:
    if isnan(value):
        return "N/A"

    return f"{value:.2f}"


if __name__ == "__main__":
    raise SystemExit(main())
