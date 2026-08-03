"""Rate of Change (ROC) indicator.

ROC measures the percentage change in price over N periods.
It captures price acceleration/deceleration:
- Rising ROC = price is accelerating upward
- Falling ROC = momentum is decelerating
- ROC crossing zero = trend change signal
"""

from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class ROCIndicator(Indicator):
    """Rate of Change: ((close - close_n_ago) / close_n_ago) * 100."""

    def __init__(self, period: int = 10):
        self.period = period

    def calculate(self, stock: Stock) -> IndicatorResult:
        closes = [bar.close for bar in stock.history]

        if len(closes) <= self.period:
            return IndicatorResult(f"ROC{self.period}", float("nan"))

        current_close = closes[-1]
        past_close = closes[-1 - self.period]

        if past_close == 0:
            return IndicatorResult(f"ROC{self.period}", float("nan"))

        roc = ((current_close - past_close) / past_close) * 100.0
        return IndicatorResult(f"ROC{self.period}", roc)
