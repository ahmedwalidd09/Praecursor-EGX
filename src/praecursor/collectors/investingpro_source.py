from datetime import date

from praecursor.collectors.collection_result import CollectionResult
from praecursor.collectors.market_data_source import MarketDataSource


class InvestingProSource(MarketDataSource):
    """Placeholder for future InvestingPro integration."""

    @property
    def name(self) -> str:
        return "investingpro"

    def fetch_history(self, symbol: str, start_date: date, end_date: date) -> CollectionResult:
        raise NotImplementedError(
            "InvestingPro may require subscription or login access, so it is deferred for now."
        )
