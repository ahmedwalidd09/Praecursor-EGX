from math import isnan

from praecursor.scoring.opportunity_score import OpportunityScore
from praecursor.workflows.scanner import ScannerRunResult, SymbolScanResult, ScannerWorkflow


WARNING_PREVIEW_LIMIT = 3


def main() -> int:
    workflow = ScannerWorkflow()
    result = workflow.run()

    print_header(result)
    print_update_summary(result)
    print_ranking(result.symbol_results)
    print_errors(result)
    print_report_location(result)

    if result.success_count == 0:
        return 1

    return 0


def print_header(result: ScannerRunResult) -> None:
    print("Praecursor-EGX scanner complete")
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


def print_ranking(results: list[SymbolScanResult]) -> None:
    print("Opportunity ranking")
    print()

    for rank, symbol_result in enumerate(results, start=1):
        score = symbol_result.opportunity_score
        print("=" * 40)
        print(f"#{rank} {score.symbol}")
        print(score.company)
        print(f"Score: {score.total_score:.0f}/{score.max_score:.0f} ({score.score_percent:.0f}%)")
        print(f"Final Predictor Score: {symbol_result.final_predictor_score:.0f}/100")
        print(f"Predictor Label: {symbol_result.predictor_label}")
        print(f"Predictor Reasons: {symbol_result.predictor_reasons_text}")
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
    indicator_names = ["EMA20", "EMA50", "EMA200", "RSI14", "AvgVolume20", "RelVolume20", "MACD", "MACDSignal", "MACDHistogram", "Momentum20", "TrendStrength", "ATR14", "ATRPercent14", "Breakout20", "Breakout50", "CloseHigh250", "NearCloseHigh250Percent", "VolumeConfirmedBreakout"]

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

    if result.markdown_report_path is None:
        print("No Markdown report was generated because no symbols were successfully analyzed.")
    else:
        print(f"Markdown report saved to: {result.markdown_report_path}")


def format_value(value: float) -> str:
    if isnan(value):
        return "N/A"

    return f"{value:.2f}"


if __name__ == "__main__":
    raise SystemExit(main())
