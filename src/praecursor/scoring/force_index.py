"""Force Index indicator.

Force Index = (Close - Previous Close) * Volume
Measures the power behind price moves.
- Positive Force Index: Buying pressure
- Negative Force Index: Selling pressure
- EMA of Force Index smooths the signal
"""

from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class ForceIndexIndicator(Indicator):
    """Force Index: price change * volume."""

    def __init__(self, period: int = 13):
        self.period = period

    def calculate(self, stock: Stock) -> IndicatorResult:
        closes = [bar.close for bar in stock.history]
        volumes = [bar.volume for bar in stock.history]

        if len(closes) <= self.period:
            return IndicatorResult(f"ForceIndex{self.period}", float("nan"))

        # Raw Force Index
        force_values = []
        for i in range(1, len(closes)):
            force = (closes[i] - closes[i - 1]) * (volumes[i] if volumes[i] is not None else 0)
            force_values.append(force)

        # Smooth with EMA
        if len(force_values) < self.period:
            return IndicatorResult(f"ForceIndex{self.period}", float("nan"))

        multiplier = 2 / (self.period + 1)
        ema = sum(force_values[:self.period]) / self.period

        for value in force_values[self.period:]:
            ema = (value - ema) * multiplier + ema

        return IndicatorResult(f"ForceIndex{self.period}", ema)


class ForceIndexRawIndicator(Indicator):
    """Raw (unsmoothed) Force Index for latest bar."""

    def __init__(self, period: int = 1):
        self.period = period

    def calculate(self, stock: Stock) -> IndicatorResult:
        closes = [bar.close for bar in stock.history]
        volumes = [bar.volume for bar in stock.history]

        if len(closes) < 2:
            return IndicatorResult("ForceIndexRaw", float("nan"))

        force = (closes[-1] - closes[-2]) * (volumes[-1] if volumes[-1] is not None else 0)
        return IndicatorResult("ForceIndexRaw", force)