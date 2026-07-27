from datetime import date

from praecursor.collectors.collection_result import CollectionResult
from praecursor.collectors.market_data_source import MarketDataSource


class OfficialEGXSource(MarketDataSource):
    """Placeholder for future official EGX integration."""

    @property
    def name(self) -> str:
        return "official_egx"

    def fetch_history(self, symbol: str, start_date: date, end_date: date) -> CollectionResult:
        raise NotImplementedError(
            "Official EGX integration is planned but not implemented yet. "
            "The official site should be added carefully because it is not a simple stable API."
        )
