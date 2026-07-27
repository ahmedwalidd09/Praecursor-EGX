from datetime import date

from praecursor.collectors.collection_result import CollectionResult
from praecursor.collectors.market_data_source import MarketDataSource
from praecursor.data.validation import PriceBarValidator
from praecursor.storage.price_cache import PriceCache


class DataManager:
    """
    Coordinates market data sources, validation, and optional caching.

    For now, it fetches data from one selected source and validates the
    returned price bars. Later, this class will compare multiple sources,
    cache results more intelligently, and assign confidence.
    """

    def __init__(
        self,
        sources: list[MarketDataSource],
        validator: PriceBarValidator | None = None,
        minimum_bars: int = 1,
        price_cache: PriceCache | None = None,
    ):
        if not sources:
            raise ValueError("DataManager requires at least one market data source.")

        self.sources = {source.name: source for source in sources}
        self.validator = validator or PriceBarValidator()
        self.minimum_bars = minimum_bars
        self.price_cache = price_cache

    def fetch_history(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        source_name: str | None = None,
    ) -> CollectionResult:
        source = self._select_source(source_name)
        collection_result = source.fetch_history(symbol, start_date, end_date)

        validation_result = self.validator.validate(
            collection_result.price_bars,
            symbol=symbol,
            minimum_bars=self.minimum_bars,
        )

        collection_result.warnings.extend(validation_result.warnings)

        if not validation_result.is_valid:
            error_text = "; ".join(validation_result.errors)
            raise ValueError(
                f"Invalid price data from {collection_result.source_name} "
                f"for {symbol}: {error_text}"
            )

        if self.price_cache is not None:
            saved_rows = self.price_cache.save(collection_result)
            collection_result.warnings.append(
                f"Saved {saved_rows} rows to SQLite cache."
            )

        return collection_result

    def _select_source(self, source_name: str | None) -> MarketDataSource:
        if source_name is None:
            return next(iter(self.sources.values()))

        if source_name not in self.sources:
            available_sources = ", ".join(sorted(self.sources))
            raise ValueError(
                f"Unknown market data source '{source_name}'. "
                f"Available sources: {available_sources}"
            )

        return self.sources[source_name]
