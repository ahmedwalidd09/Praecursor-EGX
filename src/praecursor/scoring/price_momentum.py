from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class PriceMomentumIndicator(Indicator):
    """Percentage price change over a lookback period."""

    def __init__(self, period: int = 20):
        self.period = period

    def calculate(self, stock: Stock) -> IndicatorResult:
        closes = [bar.close for bar in stock.history]

        if len(closes) <= self.period:
            return IndicatorResult(f"Momentum{self.period}", float("nan"))

        previous_close = closes[-(self.period + 1)]
        latest_close = closes[-1]

        if previous_close <= 0:
            return IndicatorResult(f"Momentum{self.period}", float("nan"))

        momentum_percent = ((latest_close / previous_close) - 1) * 100
        return IndicatorResult(f"Momentum{self.period}", momentum_percent)
