from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from praecursor.collectors.market_data_source import MarketDataSource
from praecursor.collectors.yahoo_finance_source import YahooFinanceSource
from praecursor.data.data_manager import DataManager
from praecursor.data.stock_builder import CachedStockBuilder
from praecursor.data.symbol_mapper import SymbolMapper
from praecursor.reporting.csv_report import DEFAULT_RANKING_REPORT, OpportunityRankingCSVWriter
from praecursor.scoring.opportunity_score import OpportunityScore, OpportunityScorer
from praecursor.storage.price_cache import PriceCache


@dataclass(frozen=True)
class SymbolScanResult:
    """Scanner output for one successfully analyzed symbol."""

    symbol: str
    downloaded_bars: int
    cached_bars: int
    total_cached_rows: int
    warnings: list[str]
    opportunity_score: OpportunityScore


@dataclass(frozen=True)
class ScannerRunResult:
    """Complete result of one scanner run."""

    start_date: date
    end_date: date
    source_name: str
    database_path: Path
    report_path: Path | None
    symbols: list[str]
    symbol_results: list[SymbolScanResult] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def ranked_scores(self) -> list[OpportunityScore]:
        return [result.opportunity_score for result in self.symbol_results]

    @property
    def success_count(self) -> int:
        return len(self.symbol_results)

    @property
    def error_count(self) -> int:
        return len(self.errors)


class ScannerWorkflow:
    """
    Run the complete Praecursor-EGX scanner workflow.

    The workflow updates market data, validates it, caches it, scores the
    configured symbols, ranks them, and writes a CSV report.
    """

    def __init__(
        self,
        lookback_days: int = 450,
        minimum_bars: int = 10,
        source_name: str = "yahoo_finance",
        symbol_mapper: SymbolMapper | None = None,
        price_cache: PriceCache | None = None,
        market_data_source: MarketDataSource | None = None,
        scorer: OpportunityScorer | None = None,
        report_writer: OpportunityRankingCSVWriter | None = None,
    ):
        self.lookback_days = lookback_days
        self.minimum_bars = minimum_bars
        self.source_name = source_name
        self.symbol_mapper = symbol_mapper or SymbolMapper.from_csv()
        self.price_cache = price_cache or PriceCache()
        self.market_data_source = market_data_source or YahooFinanceSource(
            symbol_mapper=self.symbol_mapper
        )
        self.scorer = scorer or OpportunityScorer()
        self.report_writer = report_writer or OpportunityRankingCSVWriter()

    def run(
        self,
        symbols: list[str] | None = None,
        end_date: date | None = None,
        report_path: Path = DEFAULT_RANKING_REPORT,
    ) -> ScannerRunResult:
        selected_end_date = end_date or date.today()
        start_date = selected_end_date - timedelta(days=self.lookback_days)
        selected_symbols = symbols or self.symbol_mapper.get_yahoo_symbols()

        data_manager = DataManager(
            sources=[self.market_data_source],
            minimum_bars=self.minimum_bars,
            price_cache=self.price_cache,
        )
        stock_builder = CachedStockBuilder(
            price_cache=self.price_cache,
            symbol_mapper=self.symbol_mapper,
            source_name=self.source_name,
        )

        symbol_results: list[SymbolScanResult] = []
        errors: dict[str, str] = {}

        for symbol in selected_symbols:
            try:
                update_result = data_manager.fetch_history(symbol, start_date, selected_end_date)
                stock = stock_builder.build(symbol, start_date, selected_end_date)
                opportunity_score = self.scorer.score(stock)
                cached_bars = self.price_cache.load(
                    symbol,
                    self.source_name,
                    start_date,
                    selected_end_date,
                )
                total_cached_rows = self.price_cache.count(symbol, self.source_name)

                symbol_results.append(
                    SymbolScanResult(
                        symbol=symbol,
                        downloaded_bars=len(update_result.price_bars),
                        cached_bars=len(cached_bars),
                        total_cached_rows=total_cached_rows,
                        warnings=update_result.warnings,
                        opportunity_score=opportunity_score,
                    )
                )
            except Exception as error:
                errors[symbol] = str(error)

        ranked_results = sorted(
            symbol_results,
            key=lambda result: result.opportunity_score.total_score,
            reverse=True,
        )
        ranked_scores = [result.opportunity_score for result in ranked_results]
        saved_report_path: Path | None = None

        if ranked_scores:
            saved_report_path = self.report_writer.write(ranked_scores, report_path)

        return ScannerRunResult(
            start_date=start_date,
            end_date=selected_end_date,
            source_name=self.source_name,
            database_path=self.price_cache.path,
            report_path=saved_report_path,
            symbols=selected_symbols,
            symbol_results=ranked_results,
            errors=errors,
        )
