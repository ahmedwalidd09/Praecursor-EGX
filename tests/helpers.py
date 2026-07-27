from datetime import datetime, timedelta

from praecursor.core.price_bar import PriceBar
from praecursor.core.stock import Stock


def build_stock(
    symbol: str = "TEST",
    days: int = 260,
    start_close: float = 10.0,
    daily_change: float = 0.1,
    start_volume: int = 1000,
    volume_step: int = 10,
) -> Stock:
    start_date = datetime(2025, 1, 1)
    stock = Stock(symbol=symbol, company="Test Company")

    for index in range(days):
        close = start_close + index * daily_change
        open_price = close - 0.05
        high = close + 0.10
        low = close - 0.10
        volume = start_volume + index * volume_step
        stock.history.append(
            PriceBar(
                date=start_date + timedelta(days=index),
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=volume,
            )
        )

    return stock
