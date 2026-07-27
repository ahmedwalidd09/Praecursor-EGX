from datetime import date

from praecursor.collectors.collection_result import CollectionResult
from praecursor.collectors.market_data_source import MarketDataSource


class MubasherSource(MarketDataSource):
    """Placeholder for future Mubasher Info integration."""

    @property
    def name(self) -> str:
        return "mubasher"

    def fetch_history(self, symbol: str, start_date: date, end_date: date) -> CollectionResult:
        raise NotImplementedError(
            "Mubasher integration is planned but not implemented yet. "
            "It is a good candidate for delayed latest-quote validation."
        )
