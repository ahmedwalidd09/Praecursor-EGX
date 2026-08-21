from datetime import date

from praecursor.core.stock import Stock
from praecursor.data.symbol_mapper import SymbolMapper
from praecursor.storage.price_cache import PriceCache


class CachedStockBuilder:
    """Build Stock objects from cached source price bars."""

    def __init__(
        self,
        price_cache: PriceCache | None = None,
        symbol_mapper: SymbolMapper | None = None,
        source_name: str = "yahoo_finance",
    ):
        self.price_cache = price_cache or PriceCache()
        self.symbol_mapper = symbol_mapper or SymbolMapper.from_csv()
        self.source_name = source_name

    def build(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> Stock:
        """Load cached bars and return one Stock object."""
        normalized_symbol = symbol.strip().upper()
        price_bars = self.price_cache.load(
            normalized_symbol,
            self.source_name,
            start_date,
            end_date,
        )

        if not price_bars:
            raise ValueError(
                f"No cached price bars found for {normalized_symbol} "
                f"from {self.source_name} between {start_date} and {end_date}."
            )

        company_name = self.symbol_mapper.get_company_name(normalized_symbol)
        try:
            sector_name = self.symbol_mapper.get_sector(normalized_symbol)
        except AttributeError:
            sector_name = "General"

        try:
            intraday_bars = self.price_cache.load_intraday(
                normalized_symbol,
                self.source_name,
                start_date,
                end_date,
            )
        except Exception:
            intraday_bars = []

        return Stock(
            symbol=normalized_symbol,
            company=company_name,
            sector=sector_name,
            history=price_bars,
            intraday_history=intraday_bars,
        )

    def build_many(
        self,
        symbols: list[str],
        start_date: date,
        end_date: date,
    ) -> list[Stock]:
        """Build Stock objects for multiple symbols."""
        return [self.build(symbol, start_date, end_date) for symbol in symbols]
