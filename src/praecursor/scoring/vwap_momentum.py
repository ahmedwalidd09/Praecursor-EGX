"""Volume-Weighted Average Price (VWAP) Momentum indicator.

Instead of simple price momentum, this weights momentum by volume.
A strong price move on high volume is far more significant than
the same move on low volume. This helps distinguish institutional
accumulation from retail noise.

VWAP_Momentum = sum(return_i * volume_i) / sum(volume_i) over N bars
"""

from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class VWAPMomentumIndicator(Indicator):
    """Volume-weighted price momentum over N bars."""

    def __init__(self, period: int = 10):
        self.period = period

    def calculate(self, stock: Stock) -> IndicatorResult:
        history = stock.history

        if len(history) <= self.period:
            return IndicatorResult(f"VWAPMom{self.period}", float("nan"))

        total_weighted_return = 0.0
        total_volume = 0.0

        for i in range(-self.period, 0):
            bar = history[i]
            prev_bar = history[i - 1]

            if prev_bar.close == 0:
                continue

            pct_return = (bar.close - prev_bar.close) / prev_bar.close
            volume = bar.volume if bar.volume is not None else 0

            total_weighted_return += pct_return * volume
            total_volume += volume

        if total_volume == 0:
            return IndicatorResult(f"VWAPMom{self.period}", float("nan"))

        # Result is the volume-weighted average return, expressed as percentage
        vwap_momentum = (total_weighted_return / total_volume) * 100.0
        return IndicatorResult(f"VWAPMom{self.period}", vwap_momentum)
