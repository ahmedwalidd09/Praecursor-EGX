from datetime import date, datetime, time, timedelta

from praecursor.collectors.collection_result import CollectionResult
from praecursor.collectors.market_data_source import MarketDataSource
from praecursor.core.price_bar import PriceBar


class FakeMarketDataSource(MarketDataSource):
    """
    Deterministic market data source for architecture testing.

    This is not production market data. It lets us test DataManager without
    depending on the internet or a real external website.
    """

    def __init__(self, source_name: str = "fake_market_data"):
        self._source_name = source_name

    @property
    def name(self) -> str:
        return self._source_name

    def fetch_history(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> CollectionResult:
        if start_date > end_date:
            return CollectionResult(
                symbol=symbol,
                source_name=self.name,
                warnings=["start_date is after end_date; no data returned."],
            )

        price_bars: list[PriceBar] = []
        current_date = start_date
        bar_number = 0

        while current_date <= end_date:
            if self._is_trading_day(current_date):
                price_bars.append(self._create_price_bar(current_date, bar_number))
                bar_number += 1

            current_date += timedelta(days=1)

        return CollectionResult(
            symbol=symbol,
            source_name=self.name,
            price_bars=price_bars,
            confidence=1.0,
        )

    def _is_trading_day(self, current_date: date) -> bool:
        # Python weekday numbers: Monday=0, Friday=4, Saturday=5.
        # EGX normally trades Sunday through Thursday.
        return current_date.weekday() not in (4, 5)

    def _create_price_bar(self, trade_date: date, bar_number: int) -> PriceBar:
        day_offset = (trade_date - date(2025, 1, 1)).days
        open_price = 100.0 + (day_offset * 0.5)
        close_price = open_price + 0.2

        return PriceBar(
            date=datetime.combine(trade_date, time.min),
            open=open_price,
            high=close_price + 0.5,
            low=open_price - 0.5,
            close=close_price,
            volume=100_000 + (day_offset * 1_000),
        )
