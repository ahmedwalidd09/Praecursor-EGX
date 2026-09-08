import json
import logging
import os
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import threading
import time
from typing import Callable, Optional
import joblib

logger = logging.getLogger(__name__)

from praecursor.collectors.collection_result import CollectionResult
from praecursor.collectors.market_data_source import MarketDataSource
from praecursor.collectors.mubasher_source import MubasherSource
from praecursor.collectors.stockanalysis_source import StockAnalysisSource
from praecursor.collectors.tradingview_source import TradingViewSource
from praecursor.consensus.price_consensus import PriceConsensusEngine, PriceConsensusResult, SourcePrice
from praecursor.core.price_bar import PriceBar
from praecursor.data.data_manager import DataManager
from praecursor.data.stock_builder import CachedStockBuilder
from praecursor.data.symbol_mapper import SymbolMapper
from praecursor.reporting.csv_report import (
    DEFAULT_NEXT_DAY_REPORT,
    DEFAULT_RANKING_REPORT,
    ScannerCSVReportWriter,
)
from praecursor.reporting.dashboard import DEFAULT_DASHBOARD_REPORT, ScannerDashboardWriter
from praecursor.reporting.markdown_report import DEFAULT_MARKDOWN_REPORT, ScannerMarkdownReportWriter
from praecursor.scoring.next_day import NextDayPrediction, calculate_next_day_prediction
from praecursor.scoring.swing import SwingPrediction, calculate_swing_prediction
from praecursor.scoring.opportunity_score import OpportunityScore, OpportunityScorer
from praecursor.storage.price_cache import PriceCache
from praecursor.storage.signal_history import SignalHistoryStore

REPORTS_ROOT = Path(__file__).resolve().parents[3] / "reports"
REPORT_ARCHIVE_DIR = REPORTS_ROOT / "archive"


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
    previous_rank: int | None = None
    rank_change: int | None = None
    override_next_day_label: str | None = None

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
    def consensus_score(self) -> float:
        if self.consensus_result is None:
            return 0.0

        return self.consensus_result.confidence_percent

    @property
    def final_predictor_score(self) -> float:
        """Composite predictor score including opportunity, consensus, and data quality."""
        return (
            self.opportunity_score.score_percent * 0.75
            + self.consensus_score * 0.15
            + self.data_quality_score * 0.10
        )

    @property
    def predictor_label(self) -> str:
        if self.consensus_result is None or not self.consensus_result.accepted:
            return "Low Confidence"

        if self.data_quality_label == "low":
            return "Low Data Quality"

        if self._is_extended_breakout():
            return "Extended Breakout"

        if self.final_predictor_score >= 75 and self.opportunity_score.score_percent >= 75:
            return "Strong Candidate"

        if self.final_predictor_score >= 60:
            return "Watchlist"

        return "Avoid"

    @property
    def predictor_reasons(self) -> list[str]:
        reasons = [
            f"Opportunity score {self.opportunity_score.score_percent:.0f}%",
            f"Consensus confidence {self.consensus_score:.0f}%",
            f"Data quality {self.data_quality_score:.0f}%",
        ]

        rsi14 = self.opportunity_score.indicator_values.get("RSI14")
        relative_volume20 = self.opportunity_score.indicator_values.get("RelVolume20")
        breakout20 = self.opportunity_score.indicator_values.get("Breakout20")
        breakout50 = self.opportunity_score.indicator_values.get("Breakout50")

        if rsi14 is not None and rsi14 == rsi14 and rsi14 > 75:
            reasons.append("RSI is overextended; entry timing risk is elevated")

        if relative_volume20 is not None and relative_volume20 == relative_volume20 and relative_volume20 < 0.75:
            reasons.append("Relative volume is weak")

        if breakout20 == 1.0 and breakout50 == 1.0:
            reasons.append("Close-based 20/50 breakout is active")

        return reasons

    @property
    def predictor_reasons_text(self) -> str:
        return "; ".join(self.predictor_reasons)

    @property
    def next_day_prediction(self) -> NextDayPrediction:
        return calculate_next_day_prediction(
            opportunity_score=self.opportunity_score,
            consensus_accepted=self.consensus_result.accepted if self.consensus_result is not None else True,
            consensus_confidence=self.consensus_score,
            data_quality_score=self.data_quality_score,
        )

    @property
    def next_day_score(self) -> float:
        return self.next_day_prediction.score

    @property
    def next_day_label(self) -> str:
        override = getattr(self, "override_next_day_label", None)
        if override:
            return override
        return self.next_day_prediction.label

    @property
    def next_day_reasons_text(self) -> str:
        return self.next_day_prediction.reasons_text

    @property
    def swing_prediction(self) -> SwingPrediction:
        return calculate_swing_prediction(
            opportunity_score=self.opportunity_score,
            consensus_accepted=self.consensus_result.accepted if self.consensus_result is not None else True,
            consensus_confidence=self.consensus_score,
            data_quality_score=self.data_quality_score,
        )

    @property
    def swing_score(self) -> float:
        return self.swing_prediction.score

    @property
    def swing_label(self) -> str:
        return self.swing_prediction.label

    @property
    def swing_stop_loss(self) -> float:
        return self.swing_prediction.stop_loss_price

    @property
    def rank_change_text(self) -> str:
        if self.previous_rank is None or self.rank_change is None:
            return "new"

        if self.rank_change > 0:
            return f"up {self.rank_change}"

        if self.rank_change < 0:
            return f"down {abs(self.rank_change)}"

        return "unchanged"

    def _is_extended_breakout(self) -> bool:
        rsi14 = self.opportunity_score.indicator_values.get("RSI14")
        breakout20 = self.opportunity_score.indicator_values.get("Breakout20")
        breakout50 = self.opportunity_score.indicator_values.get("Breakout50")
        relative_volume20 = self.opportunity_score.indicator_values.get("RelVolume20")

        if rsi14 is None or rsi14 != rsi14:
            return False

        return (
            rsi14 > 75
            and breakout20 == 1.0
            and breakout50 == 1.0
            and relative_volume20 is not None
            and relative_volume20 == relative_volume20
            and relative_volume20 >= 1.0
        )

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
    generated_at: datetime
    source_name: str
    consensus_source_names: list[str]
    database_path: Path
    report_path: Path | None
    next_day_report_path: Path | None
    markdown_report_path: Path | None
    dashboard_report_path: Path | None
    archive_report_path: Path | None
    archive_markdown_report_path: Path | None
    history_run_id: int | None
    symbols: list[str]
    symbol_results: list[SymbolScanResult] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def ranked_scores(self) -> list[OpportunityScore]:
        return [result.opportunity_score for result in self.symbol_results]

    @property
    def next_day_results(self) -> list[SymbolScanResult]:
        return sorted(self.symbol_results, key=lambda result: result.next_day_score, reverse=True)

    @property
    def swing_results(self) -> list[SymbolScanResult]:
        return sorted(self.symbol_results, key=lambda result: result.swing_score, reverse=True)

    @property
    def success_count(self) -> int:
        return len(self.symbol_results)

    @property
    def error_count(self) -> int:
        return len(self.errors)


class ScannerWorkflow:
    """Run the complete Praecursor-EGX scanner workflow."""

    def __init__(
        self,
        lookback_days: int = 1250,
        consensus_lookback_days: int = 180,
        minimum_bars: int = 10,
        source_name: str = "tradingview",
        symbol_mapper: SymbolMapper | None = None,
        price_cache: PriceCache | None = None,
        market_data_source: MarketDataSource | None = None,
        consensus_data_sources: list[MarketDataSource] | None = None,
        consensus_engine: PriceConsensusEngine | None = None,
        scorer: OpportunityScorer | None = None,
        report_writer: ScannerCSVReportWriter | None = None,
        markdown_report_writer: ScannerMarkdownReportWriter | None = None,
        dashboard_writer: ScannerDashboardWriter | None = None,
        history_store: SignalHistoryStore | None = None,
        enable_consensus: bool = True,
        enable_history: bool = True,
        enable_archive_reports: bool = True,
    ):
        self.lookback_days = lookback_days
        self.consensus_lookback_days = consensus_lookback_days
        self.minimum_bars = minimum_bars
        self.source_name = source_name
        self.symbol_mapper = symbol_mapper or SymbolMapper.from_csv()
        self.price_cache = price_cache or PriceCache()
        self.market_data_source = market_data_source or TradingViewSource(symbol_mapper=self.symbol_mapper)
        self.enable_consensus = enable_consensus
        self.consensus_data_sources = consensus_data_sources
        self.enable_history = enable_history
        self.enable_archive_reports = enable_archive_reports
        self.history_store = (
            history_store
            if history_store is not None
            else SignalHistoryStore(self.price_cache.path)
            if self.enable_history
            else None
        )

        if self.enable_consensus:
            if self.consensus_data_sources is None:
                self.consensus_data_sources = [
                    StockAnalysisSource(symbol_mapper=self.symbol_mapper),
                    MubasherSource(),
                    TradingViewSource(symbol_mapper=self.symbol_mapper),
                ]
            
            primary_name = getattr(self.market_data_source, "name", getattr(self.market_data_source, "source_name", self.source_name))
            self.consensus_data_sources = [
                src for src in self.consensus_data_sources
                if getattr(src, "name", getattr(src, "source_name", "")) != primary_name
            ]

        self.consensus_engine = consensus_engine or PriceConsensusEngine(
            tolerance_percent=0.5,
            minimum_agreeing_sources=2,
            target_source_count=5,
        )
        self.scorer = scorer or OpportunityScorer()
        self.report_writer = report_writer or ScannerCSVReportWriter()
        self.markdown_report_writer = markdown_report_writer or ScannerMarkdownReportWriter()
        self.dashboard_writer = dashboard_writer or ScannerDashboardWriter()

    def run(
        self,
        symbols: list[str] | None = None,
        end_date: date | None = None,
        report_path: Path = DEFAULT_RANKING_REPORT,
        next_day_report_path: Path = DEFAULT_NEXT_DAY_REPORT,
        markdown_report_path: Path = DEFAULT_MARKDOWN_REPORT,
        dashboard_report_path: Path = DEFAULT_DASHBOARD_REPORT,
        progress_callback: Callable[[int, int], None] | None = None,
        swing_report_path: Path | None = None,
        **kwargs,
    ) -> ScannerRunResult:
        generated_at = datetime.now(timezone.utc)

        # Auto-backfill outcomes for all prior predictions using freshly available price data
        try:
            from praecursor.analysis.accuracy_tracker import track_outcomes_from_db
            db_target = getattr(self, "price_cache", None) and getattr(self.price_cache, "path", None)
            backfilled = track_outcomes_from_db(db_path=db_target)
            if backfilled:
                logger.info(f"[AUTO-OUTCOME] Backfilled {backfilled} prediction outcomes from prior scans.")
        except Exception as e:
            logger.warning(f"[AUTO-OUTCOME] Could not backfill outcomes: {e}")

        selected_end_date = end_date or date.today()
        start_date = selected_end_date - timedelta(days=self.lookback_days)
        consensus_start_date = selected_end_date - timedelta(days=self.consensus_lookback_days)
        selected_symbols = symbols or self.symbol_mapper.get_yahoo_symbols()

        symbol_results: list[SymbolScanResult] = []
        errors: dict[str, str] = {}
        total_symbols = len(selected_symbols)
        lock = threading.Lock()
        completed_count = 0
        start_time = time.time()
        project_root = REPORTS_ROOT.parent
        data_dir = project_root / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        status_file = data_dir / "scan_status.json"

        # Initialize status file for Stage 1
        initial_status = {
            "running": True,
            "stage": 1,
            "stage_name": "Market Data & Symbol Scanner",
            "processed": 0,
            "total": total_symbols,
            "percent": 0.0,
            "current_symbol": None,
            "elapsed_seconds": 0,
            "eta_seconds": 0,
            "telegram_status": "Queued for Stage 4",
            "error": None,
            "completed": False,
        }
        try:
            tmp_init = status_file.with_suffix(".tmp")
            with open(tmp_init, "w", encoding="utf-8") as f:
                json.dump(initial_status, f, indent=2)
            os.replace(tmp_init, status_file)
        except Exception as e:
            logger.warning("Failed to write initial scan status: %s", e)

        def process_symbol(symbol: str):
            res_item = None
            try:
                local_cache = PriceCache(database_path=self.price_cache.path)
                local_primary_manager = DataManager(
                    sources=[self.market_data_source],
                    minimum_bars=self.minimum_bars,
                    price_cache=local_cache,
                )
                local_stock_builder = CachedStockBuilder(
                    price_cache=local_cache,
                    symbol_mapper=self.symbol_mapper,
                    source_name=self.source_name,
                )

                primary_result = local_primary_manager.fetch_history(symbol, start_date, selected_end_date)
                
                consensus_results = []
                consensus_source_errors = {}
                if self.enable_consensus and self.consensus_data_sources:
                    logger.info("Fetching price data for %s from consensus data sources (%s)", symbol, ", ".join(getattr(s, "name", str(s)) for s in self.consensus_data_sources))
                    for source in self.consensus_data_sources:
                        try:
                            mgr = DataManager(sources=[source], minimum_bars=1, price_cache=local_cache)
                            res = mgr.fetch_history(symbol, consensus_start_date, selected_end_date)
                            if res.price_bars:
                                consensus_results.append(res)
                            else:
                                consensus_source_errors[source.name] = "no bars"
                        except Exception as e:
                            consensus_source_errors[source.name] = str(e)

                consensus_result, consensus_error = self._calculate_consensus(
                    symbol,
                    primary_result,
                    consensus_results,
                )

                # Fix missed data: if primary source is wrong but consensus agrees, override it in cache
                if consensus_result and not consensus_result.accepted and consensus_result.confidence_percent >= 40.0:
                    local_cache.override_consensus_prices(
                        symbol,
                        self.source_name,
                        consensus_result.trade_date,
                        consensus_result.consensus_high,
                        consensus_result.consensus_close,
                    )

                stock = local_stock_builder.build(symbol, start_date, selected_end_date)
                opportunity_score = self.scorer.score(stock)
                cached_bars = local_cache.load(
                    symbol,
                    self.source_name,
                    start_date,
                    selected_end_date,
                )
                total_cached_rows = local_cache.count(symbol, self.source_name)

                warnings = list(primary_result.warnings)
                consensus_downloaded_bars = 0

                for consensus_result_data in consensus_results:
                    warnings.extend(consensus_result_data.warnings)
                    consensus_downloaded_bars += len(consensus_result_data.price_bars)

                for source_name, error in consensus_source_errors.items():
                    warnings.append(f"Consensus source {source_name} unavailable: {error}")

                if consensus_result is not None:
                    warnings.extend(consensus_result.warnings)

                res_item = SymbolScanResult(
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
                return res_item
            except Exception as error:
                res_item = (symbol, str(error))
                return res_item
            finally:
                with lock:
                    nonlocal completed_count
                    completed_count += 1
                    pct = (completed_count / total_symbols) * 100.0 if total_symbols > 0 else 100.0
                    elapsed = time.time() - start_time
                    avg_per_symbol = elapsed / completed_count if completed_count > 0 else 0
                    eta_seconds = max(0, int(avg_per_symbol * (total_symbols - completed_count)))
                    elapsed_m, elapsed_s = divmod(int(elapsed), 60)
                    eta_m, eta_s = divmod(eta_seconds, 60)
                    elapsed_str = f"{elapsed_m}m {elapsed_s}s"
                    eta_str = f"{eta_m}m {eta_s}s"
                    logger.info(
                        f"[SCAN PROGRESS] [{completed_count}/{total_symbols}] {pct:.1f}% | Scanned {symbol} | Elapsed: {elapsed_str} | ETA: {eta_str}"
                    )
                    status_data = {
                        "running": True,
                        "stage": 1,
                        "stage_name": "Market Data & Symbol Scanner",
                        "processed": completed_count,
                        "total": total_symbols,
                        "percent": round(pct, 1),
                        "current_symbol": symbol,
                        "elapsed_seconds": int(elapsed),
                        "eta_seconds": eta_seconds,
                        "telegram_status": "Queued for Stage 4",
                        "error": None,
                        "completed": False,
                    }
                    try:
                        tmp_file = status_file.with_suffix(".tmp")
                        with open(tmp_file, "w", encoding="utf-8") as f:
                            json.dump(status_data, f, indent=2)
                        os.replace(tmp_file, status_file)
                    except Exception as e:
                        logger.warning("Failed to write scan status: %s", e)
                    if progress_callback:
                        try:
                            progress_callback(completed_count, total_symbols)
                        except Exception:
                            pass

        results = joblib.Parallel(n_jobs=4, backend="threading")(
            joblib.delayed(process_symbol)(sym) for sym in selected_symbols
        )

        for res in results:
            if isinstance(res, SymbolScanResult):
                symbol_results.append(res)
            else:
                errors[res[0]] = res[1]
            
            if progress_callback:
                progress_callback(len(symbol_results) + len(errors), total_symbols)
                
        if progress_callback:
            progress_callback(total_symbols, total_symbols)

        ranked_results = sorted(
            symbol_results,
            key=lambda result: result.opportunity_score.total_score,
            reverse=True,
        )
        ranked_results = self._attach_rank_changes(ranked_results)

        saved_report_path: Path | None = None
        saved_next_day_report_path: Path | None = None
        saved_markdown_report_path: Path | None = None
        dashboard_report_path_value: Path | None = None
        archive_report_path: Path | None = None
        archive_markdown_report_path: Path | None = None

        if ranked_results:
            next_day_results = sorted(ranked_results, key=lambda result: result.next_day_score, reverse=True)
            
            # Dynamic Top-N Ranking: badge genuine elite breakout candidates (max 5) as Top Picks
            top_pick_num = 0
            for i, res in enumerate(next_day_results):
                nd_pred = res.next_day_prediction
                label = nd_pred.label
                new_label = label
                is_consensus_ok = res.consensus_result is None or res.consensus_result.accepted
                is_eligible = is_consensus_ok and ("Low Confidence" not in label) and ("Avoid" not in label)
                if nd_pred.score >= 68.0 and is_eligible and ("Candidate" in label) and top_pick_num < 5:
                    top_pick_num += 1
                    new_label = f"⭐ Top Pick #{top_pick_num} ({label})"
                if new_label != label:
                    next_day_results[i] = replace(res, override_next_day_label=new_label)
                    
            # Re-sync ranked_results so the database and dashboard get the updated objects
            modified_map = {res.symbol: res for res in next_day_results}
            ranked_results = [modified_map[res.symbol] for res in ranked_results]
                    
            saved_report_path = self.report_writer.write(ranked_results, report_path)
            saved_next_day_report_path = self.report_writer.write(next_day_results, next_day_report_path)
            saved_markdown_report_path = self.markdown_report_writer.write(
                ranked_results,
                markdown_report_path,
            )

            if self.enable_archive_reports:
                archive_report_path = self.report_writer.write(
                    ranked_results,
                    self._timestamped_report_path(generated_at, "csv"),
                )
                archive_markdown_report_path = self.markdown_report_writer.write(
                    ranked_results,
                    self._timestamped_report_path(generated_at, "md"),
                )

        result = ScannerRunResult(
            start_date=start_date,
            end_date=selected_end_date,
            generated_at=generated_at,
            source_name=self.source_name,
            consensus_source_names=[source.name for source in self.consensus_data_sources or []],
            database_path=self.price_cache.path,
            report_path=saved_report_path,
            next_day_report_path=saved_next_day_report_path,
            markdown_report_path=saved_markdown_report_path,
            dashboard_report_path=dashboard_report_path_value,
            archive_report_path=archive_report_path,
            archive_markdown_report_path=archive_markdown_report_path,
            history_run_id=None,
            symbols=selected_symbols,
            symbol_results=ranked_results,
            errors=errors,
        )

        if ranked_results:
            dashboard_report_path_value = self.dashboard_writer.write(result, dashboard_report_path)
            result = replace(result, dashboard_report_path=dashboard_report_path_value)

        if self.enable_history and self.history_store is not None:
            history_run_id = self.history_store.save_run(result)
            result = replace(result, history_run_id=history_run_id)
            logger.info(f"Saved scanner run {history_run_id} to history database.")
        
        return result

    def _attach_rank_changes(self, ranked_results: list[SymbolScanResult]) -> list[SymbolScanResult]:
        if not self.enable_history or self.history_store is None:
            return ranked_results

        previous_ranks = self.history_store.latest_ranks()
        updated_results: list[SymbolScanResult] = []

        for current_rank, result in enumerate(ranked_results, start=1):
            previous_rank = previous_ranks.get(result.symbol)
            rank_change = None

            if previous_rank is not None:
                rank_change = previous_rank - current_rank

            updated_results.append(
                replace(result, previous_rank=previous_rank, rank_change=rank_change)
            )

        return updated_results

    def _timestamped_report_path(self, generated_at: datetime, extension: str) -> Path:
        timestamp = generated_at.strftime("%Y%m%d_%H%M%S")
        return REPORT_ARCHIVE_DIR / f"opportunity_ranking_{timestamp}.{extension}"

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

        source_names = ", ".join(source.name for source in self.consensus_data_sources)
        logger.info(
            "Fetching price data for %s from consensus data sources: %s",
            symbol,
            source_names,
        )

        for source in self.consensus_data_sources:
            logger.info("Fetching price data for %s from data source: %s", symbol, source.name)
            try:
                manager = DataManager(
                    sources=[source],
                    minimum_bars=1,
                    price_cache=self.price_cache,
                )
                result = manager.fetch_history(symbol, start_date, end_date)

                if result.price_bars:
                    results.append(result)
                    logger.info(
                        "Successfully fetched %d price bar(s) for %s from source: %s",
                        len(result.price_bars),
                        symbol,
                        source.name,
                    )
                else:
                    errors[source.name] = "source returned no price bars"
                    logger.warning("No price bars returned for %s from source: %s", symbol, source.name)
            except Exception as error:
                errors[source.name] = str(error)
                logger.warning("Failed to fetch price data for %s from source %s: %s", symbol, source.name, error)

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
                    high=bar.high,
                    volume=bar.volume,
                )
            )

        return source_prices

    def _find_bar_for_date(self, price_bars: list[PriceBar], trade_date: date) -> PriceBar | None:
        for bar in price_bars:
            if bar.date.date() == trade_date:
                return bar

        return None
