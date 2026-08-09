"""Chaikin Money Flow (CMF) indicator.

CMF combines price and volume to measure buying/selling pressure over a period.
- CMF > 0: Buying pressure (accumulation)
- CMF < 0: Selling pressure (distribution)
- CMF crossing above/below zero signals trend changes
"""

from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class CMFIndicator(Indicator):
    """Chaikin Money Flow - volume-weighted accumulation/distribution."""

    def __init__(self, period: int = 20):
        self.period = period

    def calculate(self, stock: Stock) -> IndicatorResult:
        highs = [bar.high for bar in stock.history]
        lows = [bar.low for bar in stock.history]
        closes = [bar.close for bar in stock.history]
        volumes = [bar.volume for bar in stock.history]

        if len(closes) <= self.period:
            return IndicatorResult(f"CMF{self.period}", float("nan"))

        # Money Flow Multiplier = ((Close - Low) - (High - Close)) / (High - Low)
        # Money Flow Volume = Multiplier * Volume
        # CMF = Sum(Money Flow Volume) / Sum(Volume) over period

        mfv_sum = 0.0
        volume_sum = 0.0

        for i in range(-self.period, 0):
            high = highs[i]
            low = lows[i]
            close = closes[i]
            volume = volumes[i] if volumes[i] is not None else 0

            if high == low:
                multiplier = 0.0
            else:
                multiplier = ((close - low) - (high - close)) / (high - low)

            mfv = multiplier * volume
            mfv_sum += mfv
            volume_sum += volume

        if volume_sum == 0:
            return IndicatorResult(f"CMF{self.period}", float("nan"))

        cmf = mfv_sum / volume_sum

        return IndicatorResult(f"CMF{self.period}", cmf)