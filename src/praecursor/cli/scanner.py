import argparse
from datetime import datetime
from math import isnan
from pathlib import Path
import sys

from praecursor.core.settings import DEFAULT_SCANNER_SETTINGS, ScannerSettings
from praecursor.scoring.opportunity_score import OpportunityScore
from praecursor.workflows.scanner import ScannerRunResult, ScannerWorkflow, SymbolScanResult
from praecursor.data.symbol_mapper import SymbolMapper


WARNING_PREVIEW_LIMIT = 3


def main() -> int:
    args, settings = parse_args()
    
    target_date = None
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"Error: Invalid date format '{args.date}'. Expected YYYY-MM-DD.", file=sys.stderr)
            return 1

    if args.watchlist:
        symbol_mapper = SymbolMapper.from_csv(args.watchlist)
        symbols = parse_symbols(args.symbols) or symbol_mapper.get_yahoo_symbols()
    else:
        symbol_mapper = SymbolMapper.from_csv()
        symbols = parse_symbols(args.symbols) or symbol_mapper.get_yahoo_symbols()

    workflow = ScannerWorkflow(
        lookback_days=args.lookback_days,
        consensus_lookback_days=args.consensus_lookback_days,
        minimum_bars=args.minimum_bars,
        enable_consensus=not args.no_consensus,
        enable_history=not args.no_history,
        enable_archive_reports=not args.no_archive_reports,
        symbol_mapper=symbol_mapper,
    )
    result = workflow.run(symbols=symbols, end_date=target_date)

    print_header(result, settings)
    print_update_summary(result)
    print_candidate_list("Next-Day Candidates", result.next_day_results, "next_day")
    print_ranking(result.symbol_results)
    print_errors(result)
    print_report_location(result)

    print("\n---------------------------------------------------------")
    print(f"Total symbols processed: {result.success_count}")
    print(f"Errors encountered: {result.error_count}")

    if result.success_count == 0:
        return 1

    return 0


def parse_args() -> tuple[argparse.Namespace, ScannerSettings]:
    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument("--config", default=str(DEFAULT_SCANNER_SETTINGS))
    config_args, remaining_args = config_parser.parse_known_args()
    settings = ScannerSettings.from_json(config_args.config)

    parser = argparse.ArgumentParser(
        description="Run the Praecursor-EGX scanner.",
        parents=[config_parser],
    )
    parser.add_argument(
        "--symbols",
        help="Comma-separated EGX symbols to scan, for example COMI,HRHO. Defaults to config/symbols.csv.",
    )
    parser.add_argument(
        "--watchlist",
        help="Path to a custom CSV file containing a list of symbols to scan. Overrides default config/symbols.csv.",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Target end date for scanner in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=settings.lookback_days,
        help=f"Calendar days of primary history to download. Default: {settings.lookback_days}.",
    )
    parser.add_argument(
        "--consensus-lookback-days",
        type=int,
        default=settings.consensus_lookback_days,
        help=f"Calendar days to request from consensus sources. Default: {settings.consensus_lookback_days}.",
    )
    parser.add_argument(
        "--minimum-bars",
        type=int,
        default=settings.minimum_bars,
        help=f"Minimum bars required from a source. Default: {settings.minimum_bars}.",
    )
    parser.add_argument(
        "--no-consensus",
        action="store_true",
        default=not settings.enable_consensus,
        help="Disable latest-close consensus checks.",
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        default=not settings.enable_history,
        help="Do not store this scanner run in SQLite signal history.",
    )
    parser.add_argument(
        "--no-archive-reports",
        action="store_true",
        default=not settings.enable_archive_reports,
        help="Only write latest reports, not timestamped archive copies.",
    )

    return parser.parse_args(remaining_args), settings


def parse_symbols(value: str | None) -> list[str] | None:
    if not value:
        return None

    return [symbol.strip().upper() for symbol in value.split(",") if symbol.strip()]


def print_header(result: ScannerRunResult, settings: ScannerSettings) -> None:
    print("Praecursor-EGX scanner complete")
    print(f"Run ID: {result.history_run_id if result.history_run_id is not None else 'not saved'}")
    print(f"Generated at: {result.generated_at.isoformat()}")
    print(f"Config defaults: lookback={settings.lookback_days}, consensus_lookback={settings.consensus_lookback_days}")
    print(f"Database: {result.database_path}")
    print(f"Primary source: {result.source_name}")
    print(f"Consensus sources: {', '.join(result.consensus_source_names)}")
    print(f"Configured symbols: {', '.join(result.symbols)}")
    print(f"Date range: {result.start_date} to {result.end_date}")
    print(f"Successful symbols: {result.success_count}")
    print(f"Failed symbols: {result.error_count}")
    print()


def print_update_summary(result: ScannerRunResult) -> None:
    print("Data update summary")
    print()

    for symbol_result in result.symbol_results:
        score = symbol_result.opportunity_score
        print("=" * 40)
        print(symbol_result.symbol)
        print(score.company)
        print(f"Primary downloaded bars: {symbol_result.downloaded_bars}")
        print(f"Consensus downloaded bars: {symbol_result.consensus_downloaded_bars}")
        print(f"Cached bars in date range: {symbol_result.cached_bars}")
        print(f"Total cached primary rows: {symbol_result.total_cached_rows}")
        print_consensus_summary(symbol_result)
        if symbol_result.consensus_source_errors:
            print(f"Consensus source errors: {symbol_result.consensus_source_errors_text}")
        print(f"Data quality: {symbol_result.data_quality_score:.0f}% ({symbol_result.data_quality_label})")
        print(f"High/low quality: {symbol_result.high_low_quality_score:.0f}% ({symbol_result.high_low_quality_label})")
        print(f"ATR reliability: {symbol_result.atr_reliability_label}")
        print(f"Warnings: {symbol_result.warning_count}")

        for warning in symbol_result.warnings[:WARNING_PREVIEW_LIMIT]:
            print(f"  - {warning}")

        remaining_warnings = len(symbol_result.warnings) - WARNING_PREVIEW_LIMIT

        if remaining_warnings > 0:
            print(f"  ... {remaining_warnings} more warnings")

        print()


def print_consensus_summary(symbol_result: SymbolScanResult) -> None:
    consensus = symbol_result.consensus_result

    if consensus is None:
        print(f"Close consensus: unavailable ({symbol_result.consensus_error})")
        return

    source_names = symbol_result.consensus_source_names_text
    print(
        "Close consensus: "
        f"{consensus.consensus_close:.2f} on {consensus.trade_date} | "
        f"{consensus.agreeing_source_count}/{consensus.source_count} sources agree | "
        f"confidence {consensus.confidence_percent:.0f}% ({consensus.confidence_label}) | "
        f"accepted={consensus.accepted} | "
        f"sources={source_names}"
    )


def print_candidate_list(title: str, results: list[SymbolScanResult], mode: str) -> None:
    print(title)
    print()

    for rank, symbol_result in enumerate(results, start=1):
        score = symbol_result.opportunity_score
        candidate_score = symbol_result.next_day_score
        candidate_label = symbol_result.next_day_label
        candidate_reasons = symbol_result.next_day_reasons_text

        print("=" * 40)
        print(f"#{rank} {score.symbol} - {score.company}")
        print(f"{title[:-1]} Score: {candidate_score:.0f}/100")
        print(f"Label: {candidate_label}")
        print(f"Reasons: {candidate_reasons}")
        print(f"Latest Close: {score.latest_close:.2f}")
        print_consensus_summary(symbol_result)
        print()


def print_ranking(results: list[SymbolScanResult]) -> None:
    print("Overall Opportunity Ranking")
    print()

    for rank, symbol_result in enumerate(results, start=1):
        score = symbol_result.opportunity_score
        print("=" * 40)
        print(f"#{rank} {score.symbol}")
        print(score.company)
        print(f"Previous Rank: {symbol_result.previous_rank if symbol_result.previous_rank is not None else 'new'}")
        print(f"Rank Change: {symbol_result.rank_change_text}")
        print(f"Score: {score.total_score:.0f}/{score.max_score:.0f} ({score.score_percent:.0f}%)")
        print(f"Final Predictor Score: {symbol_result.final_predictor_score:.0f}/100")
        print(f"Predictor Label: {symbol_result.predictor_label}")
        print(f"Predictor Reasons: {symbol_result.predictor_reasons_text}")
        print(f"Next-Day Score: {symbol_result.next_day_score:.0f}/100")
        print(f"Next-Day Label: {symbol_result.next_day_label}")
        print(f"Next-Day Reasons: {symbol_result.next_day_reasons_text}")
        print(f"Latest Close: {score.latest_close:.2f}")
        print_consensus_summary(symbol_result)
        print_indicator_values(score)
        print("Components:")

        for component in score.components:
            print(
                f"  - {component.name}: "
                f"{component.score:.0f}/{component.max_score:.0f} - {component.reason}"
            )

        print()


def print_indicator_values(score: OpportunityScore) -> None:
    indicator_names = ["EMA20", "EMA50", "EMA200", "RSI14", "AvgVolume20", "RelVolume20", "MACD", "MACDSignal", "MACDHistogram", "Momentum20", "TrendStrength", "ATR14", "ATRPercent14", "Breakout20", "Breakout50", "CloseHigh250", "NearCloseHigh250Percent", "VolumeConfirmedBreakout", "RSIRebound", "EMA20Reclaim", "MACDHistogramImprovement", "VolumeSpikeFromWeakness", "Momentum5"]

    for indicator_name in indicator_names:
        value = score.indicator_values.get(indicator_name, float("nan"))
        print(f"{indicator_name}: {format_value(value)}")


def print_errors(result: ScannerRunResult) -> None:
    if not result.errors:
        return

    print("Errors")
    print()

    for symbol, error in result.errors.items():
        print(f"{symbol}: {error}")

    print()


def print_report_location(result: ScannerRunResult) -> None:
    if result.report_path is None:
        print("No CSV report was generated because no symbols were successfully analyzed.")
    else:
        print(f"CSV report saved to: {result.report_path}")

    if result.next_day_report_path is not None:
        print(f"Next-day candidates CSV saved to: {result.next_day_report_path}")

    if result.markdown_report_path is None:
        print("No Markdown report was generated because no symbols were successfully analyzed.")
    else:
        print(f"Markdown report saved to: {result.markdown_report_path}")

    if result.dashboard_report_path is not None:
        print(f"Dashboard saved to: {result.dashboard_report_path}")

    if result.archive_report_path is not None:
        print(f"Timestamped CSV archived to: {result.archive_report_path}")

    if result.archive_markdown_report_path is not None:
        print(f"Timestamped Markdown archived to: {result.archive_markdown_report_path}")


def format_value(value: float) -> str:
    if isnan(value):
        return "N/A"

    return f"{value:.2f}"


if __name__ == "__main__":
    raise SystemExit(main())
