import argparse
import csv
from datetime import date, timedelta
from pathlib import Path

from praecursor.collectors.stockanalysis_source import StockAnalysisSource
from praecursor.collectors.yahoo_finance_source import YahooFinanceSource
from praecursor.collectors.mubasher_source import MubasherSource
from praecursor.data.data_manager import DataManager
from praecursor.data.symbol_mapper import SymbolMapper


LOOKBACK_DAYS = 60
MINIMUM_BARS = 1
ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = ROOT / "reports"


def main() -> int:
    args = parse_args()
    symbol_mapper = SymbolMapper.from_csv()
    symbols = parse_symbols(args.symbols) or symbol_mapper.get_symbols(include_disabled=args.include_disabled)

    if args.limit:
        symbols = symbols[: args.limit]

    start_date = date.today() - timedelta(days=args.lookback_days)
    end_date = date.today()

    yahoo = DataManager(
        sources=[YahooFinanceSource(symbol_mapper=symbol_mapper)],
        minimum_bars=MINIMUM_BARS,
    )
    stockanalysis = DataManager(
        sources=[StockAnalysisSource(symbol_mapper=symbol_mapper)],
        minimum_bars=MINIMUM_BARS,
    )
    mubasher = DataManager(
        sources=[MubasherSource()],
        minimum_bars=MINIMUM_BARS,
    )

    print("Checking configured symbol availability")
    print(f"Symbols checked: {len(symbols)}")
    print(f"Date range: {start_date} to {end_date}")
    print()
    print(f"{'Symbol':<8} {'Enabled':<8} {'Yahoo':<12} {'StockAnalysis':<14} {'Mubasher':<12} Notes")
    print("-" * 120)

    failures = 0
    results = []
    disabled_count = 0

    for symbol in symbols:
        yahoo_status, yahoo_note = check_source(yahoo, symbol, start_date, end_date)
        stockanalysis_status, stockanalysis_note = check_source(stockanalysis, symbol, start_date, end_date)
        mubasher_status, mubasher_note = check_source(mubasher, symbol, start_date, end_date)
        
        # Determine overall failure (if both primary sources fail)
        if yahoo_status != "ok" and stockanalysis_status != "ok":
            failures += 1
            if args.auto_disable:
                symbol_mapper.disable_symbol(symbol)
                disabled_count += 1
        
        notes = "; ".join(note for note in [yahoo_note, stockanalysis_note, mubasher_note] if note)
        enabled = str(symbol_mapper.is_enabled(symbol))
        
        results.append({
            "symbol": symbol,
            "enabled": enabled,
            "yahoo": yahoo_status,
            "stockanalysis": stockanalysis_status,
            "mubasher": mubasher_status,
            "notes": notes,
        })
        
        print(
            f"{symbol:<8} "
            f"{enabled:<8} "
            f"{yahoo_status:<12} "
            f"{stockanalysis_status:<14} "
            f"{mubasher_status:<12} "
            f"{notes}"
        )

    print()
    print(f"Availability failures (both Yahoo and StockAnalysis): {failures}")
    
    if args.auto_disable and disabled_count > 0:
        symbol_mapper.save()
        print(f"Auto-disabled {disabled_count} symbols and saved config/symbols.csv.")

    if args.output_report:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_path = REPORTS_DIR / "symbol_availability.csv"
        with report_path.open(mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["symbol", "enabled", "yahoo", "stockanalysis", "mubasher", "notes"])
            writer.writeheader()
            writer.writerows(results)
        print(f"Saved availability report to {report_path}")

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check source availability for configured EGX symbols.")
    parser.add_argument("--symbols", help="Comma-separated symbols to check, e.g. COMI,SWDY.")
    parser.add_argument("--limit", type=int, help="Check only the first N configured symbols.")
    parser.add_argument("--lookback-days", type=int, default=LOOKBACK_DAYS)
    parser.add_argument("--include-disabled", action="store_true")
    parser.add_argument("--auto-disable", action="store_true", help="Automatically disable symbols that fail on both Yahoo and StockAnalysis.")
    parser.add_argument("--output-report", action="store_true", help="Write a CSV report of the results.")
    return parser.parse_args()


def parse_symbols(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [symbol.strip().upper() for symbol in value.split(",") if symbol.strip()]


def check_source(manager: DataManager, symbol: str, start_date: date, end_date: date) -> tuple[str, str]:
    try:
        result = manager.fetch_history(symbol, start_date, end_date)
        if not result.price_bars:
            return "failed", f"{result.source_name} returned no data"
        latest = result.price_bars[-1]
        return "ok", f"{result.source_name} latest {latest.date.date()}"
    except Exception as error:
        return "failed", str(error)


if __name__ == "__main__":
    raise SystemExit(main())
