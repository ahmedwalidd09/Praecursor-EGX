import argparse
from datetime import date, timedelta

from praecursor.backtesting.engine import Backtester, BacktestResult
from praecursor.backtesting.reports import BacktestCSVReportWriter
from praecursor.collectors.yahoo_finance_source import YahooFinanceSource
from praecursor.data.data_manager import DataManager
from praecursor.data.symbol_mapper import SymbolMapper
from praecursor.storage.price_cache import PriceCache


def main() -> int:
    args = parse_args()
    symbol_mapper = SymbolMapper.from_csv()
    symbols = parse_symbols(args.symbols) or symbol_mapper.get_yahoo_symbols()
    end_date = date.today()
    start_date = end_date - timedelta(days=args.lookback_days)
    horizons = tuple(args.horizons)
    cache = PriceCache()

    if args.prepare_cache:
        prepare_cache(symbols, start_date, end_date, symbol_mapper, cache)

    backtester = Backtester(
        price_cache=cache,
        symbol_mapper=symbol_mapper,
        minimum_history_bars=args.minimum_history_bars,
        horizons=horizons,
        minimum_signals_per_label=args.minimum_signals_per_label,
        best_worst_limit=args.best_worst_limit,
        missed_move_threshold=args.missed_move_threshold,
        flat_return_threshold_percent=args.flat_return_threshold_percent,
        zero_volume_threshold_percent=args.zero_volume_threshold_percent,
    )
    result = backtester.run(symbols, start_date, end_date)

    report_writer = BacktestCSVReportWriter()
    report_paths = report_writer.write_all(result)

    print_header(result)
    print_errors(result)
    print_calibration_notes(result)
    print_summary(result)
    print_symbol_summary(result)
    print_score_bucket_summary(result)
    print_missed_and_overextension_counts(result)
    print_best_worst(result)
    print_report_paths(report_paths)

    if not result.signals:
        return 1

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a simple Praecursor-EGX historical signal backtest.")
    parser.add_argument(
        "--symbols",
        help="Comma-separated EGX symbols to backtest. Defaults to enabled config/symbols.csv.",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=900,
        help="Calendar days to load from cache. Default: 900.",
    )
    parser.add_argument(
        "--minimum-history-bars",
        type=int,
        default=260,
        help="Bars required before generating a historical signal. Default: 260.",
    )
    parser.add_argument(
        "--minimum-signals-per-label",
        type=int,
        default=10,
        help="Warn when a label has fewer signals than this. Default: 10.",
    )
    parser.add_argument(
        "--best-worst-limit",
        type=int,
        default=10,
        help="Number of best/worst signal examples to export. Default: 10.",
    )
    parser.add_argument(
        "--horizons",
        type=int,
        nargs="+",
        default=[1, 2, 5, 10, 20],
        help="Forward-return horizons in bars. Default: 1 2 5 10 20.",
    )
    parser.add_argument(
        "--missed-move-threshold",
        type=float,
        default=5.0,
        help="1-bar return threshold for missed mover report. Default: 5.0.",
    )
    parser.add_argument(
        "--flat-return-threshold-percent",
        type=float,
        default=80.0,
        help="Flag data as flat when unchanged close ratio reaches this percent. Default: 80.",
    )
    parser.add_argument(
        "--zero-volume-threshold-percent",
        type=float,
        default=20.0,
        help="Flag data when zero-volume bar ratio reaches this percent. Default: 20.",
    )
    parser.add_argument(
        "--prepare-cache",
        action="store_true",
        help="Download/cache Yahoo data for the requested backtest range before running.",
    )
    return parser.parse_args()


def parse_symbols(value: str | None) -> list[str] | None:
    if not value:
        return None

    return [symbol.strip().upper() for symbol in value.split(",") if symbol.strip()]


def prepare_cache(
    symbols: list[str],
    start_date: date,
    end_date: date,
    symbol_mapper: SymbolMapper,
    cache: PriceCache,
) -> None:
    print("Preparing cache with Yahoo Finance data")
    manager = DataManager(
        sources=[YahooFinanceSource(symbol_mapper=symbol_mapper)],
        minimum_bars=1,
        price_cache=cache,
    )

    for symbol in symbols:
        try:
            result = manager.fetch_history(symbol, start_date, end_date)
            print(f"- {symbol}: cached {len(result.price_bars)} bars")
        except Exception as error:
            print(f"- {symbol}: cache preparation failed: {error}")

    print()


def print_header(result: BacktestResult) -> None:
    print("Praecursor-EGX backtest complete")
    print(f"Source: {result.source_name}")
    print(f"Symbols: {', '.join(result.symbols)}")
    print(f"Date range: {result.start_date} to {result.end_date}")
    print(f"Horizons: {', '.join(str(horizon) for horizon in result.horizons)} bars")
    print(f"Signals: {len(result.signals)}")
    print(f"Errors: {len(result.errors)}")
    print()


def print_errors(result: BacktestResult) -> None:
    if not result.errors:
        return

    print("Errors")
    for symbol, error in result.errors.items():
        print(f"- {symbol}: {error}")
    print()


def print_calibration_notes(result: BacktestResult) -> None:
    if not result.calibration_notes:
        return

    print("Calibration notes")
    for note in result.calibration_notes:
        print(f"- {note}")
    print()


def print_summary(result: BacktestResult) -> None:
    if not result.summary:
        print("No backtest summary available. Run with --prepare-cache or run the scanner first.")
        print()
        return

    print("Summary by label")
    print()

    for row in result.summary:
        print("=" * 40)
        print(row.label)
        print(f"Signals: {row.signal_count}")
        if row.warning:
            print(f"Warning: {row.warning}")
        for horizon in result.horizons:
            print(
                f"{horizon}-bar avg return: {row.average_returns[horizon]:.2f}% | "
                f"win rate: {row.win_rates[horizon]:.0f}%"
            )
        print()


def print_symbol_summary(result: BacktestResult) -> None:
    if not result.symbol_summary:
        return

    print("Summary by symbol")
    print()

    for row in result.symbol_summary:
        print("=" * 40)
        print(row.symbol)
        print(f"Signals: {row.signal_count}")
        for horizon in result.horizons:
            print(
                f"{horizon}-bar avg return: {row.average_returns[horizon]:.2f}% | "
                f"win rate: {row.win_rates[horizon]:.0f}%"
            )
        print()


def print_score_bucket_summary(result: BacktestResult) -> None:
    if not result.score_bucket_summary:
        return

    print("Summary by score bucket")
    print()

    for row in result.score_bucket_summary:
        print("=" * 40)
        print(row.bucket)
        print(f"Signals: {row.signal_count}")
        if row.warning:
            print(f"Warning: {row.warning}")
        for horizon in result.horizons:
            print(
                f"{horizon}-bar avg return: {row.average_returns[horizon]:.2f}% | "
                f"win rate: {row.win_rates[horizon]:.0f}%"
            )
        print()


def print_missed_and_overextension_counts(result: BacktestResult) -> None:
    print("Calibration report counts")
    print(f"Missed next-day movers: {len(result.missed_movers)}")
    print(f"Overextension follow-through samples: {len(result.overextension_signals)}")
    print(f"Data issues: {len(result.data_issues)}")
    print()


def print_best_worst(result: BacktestResult) -> None:
    if not result.best_signals or not result.worst_signals:
        return

    example_horizon = max(result.horizons)
    print(f"Best {example_horizon}-bar signal examples")
    for signal in result.best_signals[:5]:
        print(
            f"- {signal.symbol} {signal.signal_date} {signal.label}: "
            f"{signal.forward_returns[example_horizon]:.2f}%"
        )

    print()
    print(f"Worst {example_horizon}-bar signal examples")
    for signal in result.worst_signals[:5]:
        print(
            f"- {signal.symbol} {signal.signal_date} {signal.label}: "
            f"{signal.forward_returns[example_horizon]:.2f}%"
        )
    print()


def print_report_paths(report_paths: dict[str, object]) -> None:
    print("Backtest reports")
    for name, path in report_paths.items():
        print(f"- {name}: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
