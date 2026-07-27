from datetime import date

from praecursor.collectors.collection_result import CollectionResult
from praecursor.collectors.market_data_source import MarketDataSource


class TradingViewSource(MarketDataSource):
    """Placeholder for future TradingView integration."""

    @property
    def name(self) -> str:
        return "tradingview"

    def fetch_history(self, symbol: str, start_date: date, end_date: date) -> CollectionResult:
        raise NotImplementedError(
            "TradingView integration requires terms-of-use and technical research before implementation."
        )
