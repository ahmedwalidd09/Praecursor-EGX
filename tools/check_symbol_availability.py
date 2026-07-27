from datetime import date, timedelta

from praecursor.collectors.stockanalysis_source import StockAnalysisSource
from praecursor.collectors.yahoo_finance_source import YahooFinanceSource
from praecursor.data.data_manager import DataManager
from praecursor.data.symbol_mapper import SymbolMapper


LOOKBACK_DAYS = 60
MINIMUM_BARS = 1


def main() -> int:
    symbol_mapper = SymbolMapper.from_csv()
    symbols = symbol_mapper.get_yahoo_symbols(include_disabled=True)
    start_date = date.today() - timedelta(days=LOOKBACK_DAYS)
    end_date = date.today()

    yahoo = DataManager(
        sources=[YahooFinanceSource(symbol_mapper=symbol_mapper)],
        minimum_bars=MINIMUM_BARS,
    )
    stockanalysis = DataManager(
        sources=[StockAnalysisSource(symbol_mapper=symbol_mapper)],
        minimum_bars=MINIMUM_BARS,
    )

    print("Checking configured symbol availability")
    print(f"Symbols: {', '.join(symbols)}")
    print(f"Date range: {start_date} to {end_date}")
    print()
    print(f"{'Symbol':<8} {'Enabled':<8} {'Yahoo':<12} {'StockAnalysis':<14} Notes")
    print("-" * 80)

    for symbol in symbols:
        yahoo_status, yahoo_note = check_source(yahoo, symbol, start_date, end_date)
        stockanalysis_status, stockanalysis_note = check_source(stockanalysis, symbol, start_date, end_date)
        notes = "; ".join(note for note in [yahoo_note, stockanalysis_note] if note)
        print(
            f"{symbol:<8} "
            f"{str(symbol_mapper.is_enabled(symbol)):<8} "
            f"{yahoo_status:<12} "
            f"{stockanalysis_status:<14} "
            f"{notes}"
        )

    return 0


def check_source(manager: DataManager, symbol: str, start_date: date, end_date: date) -> tuple[str, str]:
    try:
        result = manager.fetch_history(symbol, start_date, end_date)
        latest = result.price_bars[-1]
        return "ok", f"{result.source_name} latest {latest.date.date()}"
    except Exception as error:
        return "failed", str(error)


if __name__ == "__main__":
    raise SystemExit(main())
