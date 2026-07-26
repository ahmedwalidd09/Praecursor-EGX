from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class EMAIndicator(Indicator):

    def __init__(self, period: int):
        self.period = period

    def calculate(self, stock: Stock):

        closes = [bar.close for bar in stock.history]

        if len(closes) < self.period:
            return IndicatorResult(
                f"EMA{self.period}",
                float("nan"),
            )

        multiplier = 2 / (self.period + 1)

        ema = sum(closes[:self.period]) / self.period

        for price in closes[self.period:]:
            ema = (price - ema) * multiplier + ema

        return IndicatorResult(
            f"EMA{self.period}",
            ema,
        )