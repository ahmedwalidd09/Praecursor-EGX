from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from praecursor.collectors.collection_result import CollectionResult
from praecursor.collectors.market_data_source import MarketDataSource
from praecursor.collectors.mubasher_source import MubasherSource
from praecursor.collectors.stockanalysis_source import StockAnalysisSource
from praecursor.collectors.yahoo_finance_source import YahooFinanceSource
from praecursor.consensus.price_consensus import PriceConsensusEngine, PriceConsensusResult, SourcePrice
from praecursor.core.price_bar import PriceBar
from praecursor.data.data_manager import DataManager
from praecursor.data.stock_builder import CachedStockBuilder
from praecursor.data.symbol_mapper import SymbolMapper
from praecursor.reporting.csv_report import DEFAULT_RANKING_REPORT, ScannerCSVReportWriter
from praecursor.reporting.markdown_report import DEFAULT_MARKDOWN_REPORT, ScannerMarkdownReportWriter
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
    consensus_downloaded_bars: int = 0
    consensus_source_names: list[str] = field(default_factory=list)
    consensus_source_errors: dict[str, str] = field(default_factory=dict)
    consensus_result: PriceConsensusResult | None = None
    consensus_error: str | None = None

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    @property
    def total_downloaded_bars(self) -> int:
        return self.downloaded_bars + self.consensus_downloaded_bars

    @property
    def data_quality_score(self) -> float:
        """Simple warning-rate based quality score from 0 to 100."""
        if self.total_downloaded_bars <= 0:
            return 0.0

        warning_rate_percent = (self.warning_count / self.total_downloaded_bars) * 100
        return max(0.0, 100.0 - warning_rate_percent)

    @property
    def data_quality_label(self) -> str:
        if self.data_quality_score >= 80:
            return "high"

        if self.data_quality_score >= 60:
            return "medium"

        return "low"

    @property
    def high_low_warning_count(self) -> int:
        return sum(
            1
            for warning in self.warnings
            if "adjusted high/low range" in warning.lower()
        )

    @property
    def high_low_quality_score(self) -> float:
        if self.total_downloaded_bars <= 0:
            return 0.0

        warning_rate_percent = (self.high_low_warning_count / self.total_downloaded_bars) * 100
        return max(0.0, 100.0 - warning_rate_percent)

    @property
    def high_low_quality_label(self) -> str:
        if self.high_low_quality_score >= 80:
            return "high"

        if self.high_low_quality_score >= 60:
            return "medium"

        return "low"

    @property
    def atr_reliability_label(self) -> str:
        if self.high_low_quality_score >= 80:
            return "usable"

        if self.high_low_quality_score >= 60:
            return "caution"

        return "do_not_use"

    @property
    def consensus_source_names_text(self) -> str:
        if not self.consensus_result:
            return ""

        return ", ".join(agreement.source_name for agreement in self.consensus_result.agreements)

    @property
    def consensus_source_errors_text(self) -> str:
        if not self.consensus_source_errors:
            return ""

        return "; ".join(
            f"{source}: {error}"
            for source, error in self.consensus_source_errors.items()
        )


@dataclass(frozen=True)
class ScannerRunResult:
    """Complete result of one scanner run."""

    start_date: date
    end_date: date
    source_name: str
    consensus_source_names: list[str]
    database_path: Path
    report_path: Path | None
    markdown_report_path: Path | None
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

    The workflow updates market data, validates it, caches it, scores symbols,
    checks latest-close consensus, ranks opportunities, and writes reports.
    """

    def __init__(
        self,
        lookback_days: int = 450,
        consensus_lookback_days: int = 180,
        minimum_bars: int = 10,
        source_name: str = "yahoo_finance",
        symbol_mapper: SymbolMapper | None = None,
        price_cache: PriceCache | None = None,
        market_data_source: MarketDataSource | None = None,
        consensus_data_sources: list[MarketDataSource] | None = None,
        consensus_engine: PriceConsensusEngine | None = None,
        scorer: OpportunityScorer | None = None,
        report_writer: ScannerCSVReportWriter | None = None,
        markdown_report_writer: ScannerMarkdownReportWriter | None = None,
        enable_consensus: bool = True,
    ):
        self.lookback_days = lookback_days
        self.consensus_lookback_days = consensus_lookback_days
        self.minimum_bars = minimum_bars
        self.source_name = source_name
        self.symbol_mapper = symbol_mapper or SymbolMapper.from_csv()
        self.price_cache = price_cache or PriceCache()
        self.market_data_source = market_data_source or YahooFinanceSource(
            symbol_mapper=self.symbol_mapper
        )
        self.enable_consensus = enable_consensus
        self.consensus_data_sources = consensus_data_sources

        if self.enable_consensus and self.consensus_data_sources is None:
            self.consensus_data_sources = [
                StockAnalysisSource(symbol_mapper=self.symbol_mapper),
                MubasherSource(),
            ]

        self.consensus_engine = consensus_engine or PriceConsensusEngine(
            tolerance_percent=0.5,
            minimum_agreeing_sources=2,
            target_source_count=5,
        )
        self.scorer = scorer or OpportunityScorer()
        self.report_writer = report_writer or ScannerCSVReportWriter()
        self.markdown_report_writer = markdown_report_writer or ScannerMarkdownReportWriter()

    def run(
        self,
        symbols: list[str] | None = None,
        end_date: date | None = None,
        report_path: Path = DEFAULT_RANKING_REPORT,
        markdown_report_path: Path = DEFAULT_MARKDOWN_REPORT,
    ) -> ScannerRunResult:
        selected_end_date = end_date or date.today()
        start_date = selected_end_date - timedelta(days=self.lookback_days)
        consensus_start_date = selected_end_date - timedelta(days=self.consensus_lookback_days)
        selected_symbols = symbols or self.symbol_mapper.get_yahoo_symbols()

        primary_manager = DataManager(
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
                primary_result = primary_manager.fetch_history(symbol, start_date, selected_end_date)
                consensus_results, consensus_source_errors = self._fetch_consensus_results(
                    symbol,
                    consensus_start_date,
                    selected_end_date,
                )
                stock = stock_builder.build(symbol, start_date, selected_end_date)
                opportunity_score = self.scorer.score(stock)
                cached_bars = self.price_cache.load(
                    symbol,
                    self.source_name,
                    start_date,
                    selected_end_date,
                )
                total_cached_rows = self.price_cache.count(symbol, self.source_name)
                consensus_result, consensus_error = self._calculate_consensus(
                    symbol,
                    primary_result,
                    consensus_results,
                )

                warnings = list(primary_result.warnings)
                consensus_downloaded_bars = 0

                for consensus_result_data in consensus_results:
                    warnings.extend(consensus_result_data.warnings)
                    consensus_downloaded_bars += len(consensus_result_data.price_bars)

                for source_name, error in consensus_source_errors.items():
                    warnings.append(f"Consensus source {source_name} unavailable: {error}")

                if consensus_result is not None:
                    warnings.extend(consensus_result.warnings)

                symbol_results.append(
                    SymbolScanResult(
                        symbol=symbol,
                        downloaded_bars=len(primary_result.price_bars),
                        cached_bars=len(cached_bars),
                        total_cached_rows=total_cached_rows,
                        warnings=warnings,
                        opportunity_score=opportunity_score,
                        consensus_downloaded_bars=consensus_downloaded_bars,
                        consensus_source_names=[result.source_name for result in consensus_results],
                        consensus_source_errors=consensus_source_errors,
                        consensus_result=consensus_result,
                        consensus_error=consensus_error,
                    )
                )
            except Exception as error:
                errors[symbol] = str(error)

        ranked_results = sorted(
            symbol_results,
            key=lambda result: result.opportunity_score.total_score,
            reverse=True,
        )
        saved_report_path: Path | None = None
        saved_markdown_report_path: Path | None = None

        if ranked_results:
            saved_report_path = self.report_writer.write(ranked_results, report_path)
            saved_markdown_report_path = self.markdown_report_writer.write(
                ranked_results,
                markdown_report_path,
            )

        return ScannerRunResult(
            start_date=start_date,
            end_date=selected_end_date,
            source_name=self.source_name,
            consensus_source_names=[source.name for source in self.consensus_data_sources or []],
            database_path=self.price_cache.path,
            report_path=saved_report_path,
            markdown_report_path=saved_markdown_report_path,
            symbols=selected_symbols,
            symbol_results=ranked_results,
            errors=errors,
        )

    def _fetch_consensus_results(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> tuple[list[CollectionResult], dict[str, str]]:
        if not self.enable_consensus or not self.consensus_data_sources:
            return [], {}

        results: list[CollectionResult] = []
        errors: dict[str, str] = {}

        for source in self.consensus_data_sources:
            try:
                manager = DataManager(
                    sources=[source],
                    minimum_bars=1,
                    price_cache=self.price_cache,
                )
                result = manager.fetch_history(symbol, start_date, end_date)

                if result.price_bars:
                    results.append(result)
                else:
                    errors[source.name] = "source returned no price bars"
            except Exception as error:
                errors[source.name] = str(error)

        return results, errors

    def _calculate_consensus(
        self,
        symbol: str,
        primary_result: CollectionResult,
        consensus_results: list[CollectionResult],
    ) -> tuple[PriceConsensusResult | None, str | None]:
        if not consensus_results:
            return None, "No consensus sources returned data."

        candidate_dates = sorted(
            {bar.date.date() for bar in primary_result.price_bars},
            reverse=True,
        )

        for candidate_date in candidate_dates:
            source_prices = self._build_source_prices(
                symbol,
                candidate_date,
                [primary_result, *consensus_results],
            )

            if len(source_prices) >= 2:
                try:
                    return self.consensus_engine.calculate(symbol, candidate_date, source_prices), None
                except Exception as error:
                    return None, str(error)

        return None, "No trade date had at least two source prices for consensus."

    def _build_source_prices(
        self,
        symbol: str,
        trade_date: date,
        results: list[CollectionResult],
    ) -> list[SourcePrice]:
        source_prices: list[SourcePrice] = []

        for result in results:
            bar = self._find_bar_for_date(result.price_bars, trade_date)

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

    def _find_bar_for_date(self, price_bars: list[PriceBar], trade_date: date) -> PriceBar | None:
        for bar in price_bars:
            if bar.date.date() == trade_date:
                return bar

        return None
