import argparse
from datetime import date, timedelta

from praecursor.backtesting.engine import Backtester, BacktestResult
from praecursor.backtesting.reports import BacktestCSVReportWriter
from praecursor.data.symbol_mapper import SymbolMapper


def main() -> int:
    args = parse_args()
    symbol_mapper = SymbolMapper.from_csv()
    symbols = parse_symbols(args.symbols) or symbol_mapper.get_yahoo_symbols()
    end_date = date.today()
    start_date = end_date - timedelta(days=args.lookback_days)
    horizons = tuple(args.horizons)

    backtester = Backtester(
        symbol_mapper=symbol_mapper,
        minimum_history_bars=args.minimum_history_bars,
        horizons=horizons,
    )
    result = backtester.run(symbols, start_date, end_date)

    report_writer = BacktestCSVReportWriter()
    signals_path = report_writer.write_signals(result)
    summary_path = report_writer.write_summary(result)

    print_header(result)
    print_errors(result)
    print_summary(result)
    print(f"Backtest signals saved to: {signals_path}")
    print(f"Backtest summary saved to: {summary_path}")

    if not result.signals:
        return 1

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a simple Praecursor-EGX historical signal backtest.")
    parser.add_argument(
        "--symbols",
        help="Comma-separated EGX symbols to backtest. Defaults to config/symbols.csv.",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=700,
        help="Calendar days to load from cache. Default: 700.",
    )
    parser.add_argument(
        "--minimum-history-bars",
        type=int,
        default=260,
        help="Bars required before generating a historical signal. Default: 260.",
    )
    parser.add_argument(
        "--horizons",
        type=int,
        nargs="+",
        default=[5, 10, 20],
        help="Forward-return horizons in bars. Default: 5 10 20.",
    )
    return parser.parse_args()


def parse_symbols(value: str | None) -> list[str] | None:
    if not value:
        return None

    return [symbol.strip().upper() for symbol in value.split(",") if symbol.strip()]


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


def print_summary(result: BacktestResult) -> None:
    if not result.summary:
        print("No backtest summary available. Run the scanner first to populate more cached history.")
        print()
        return

    print("Summary by label")
    print()

    for row in result.summary:
        print("=" * 40)
        print(row.label)
        print(f"Signals: {row.signal_count}")
        for horizon in result.horizons:
            print(
                f"{horizon}-bar avg return: {row.average_returns[horizon]:.2f}% | "
                f"win rate: {row.win_rates[horizon]:.0f}%"
            )
        print()


if __name__ == "__main__":
    raise SystemExit(main())
