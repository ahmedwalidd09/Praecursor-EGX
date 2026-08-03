from abc import ABC, abstractmethod
from datetime import date

from praecursor.collectors.collection_result import CollectionResult


class MarketDataError(Exception):
    """Base exception for market data collector errors."""
    pass


class NetworkError(MarketDataError):
    """Raised when network connectivity fails during data fetch."""
    pass


class MarketDataSource(ABC):
    """
    Common interface for every market data source.

    Each source will fetch historical daily price data in its own way,
    but the rest of the application will call the same method and receive
    the same CollectionResult structure.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable source name, for example: 'yahoo_finance'."""
        pass

    @abstractmethod
    def fetch_history(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> CollectionResult:
        """
        Fetch historical daily OHLCV bars for one EGX symbol.

        The symbol should be the application's normal EGX symbol, such as
        'COMI' or 'HRHO'. Source-specific symbol mapping will be handled
        by each source implementation later.
        """
        pass
