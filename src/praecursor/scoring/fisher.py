"""Fisher Transform indicator.

Fisher Transform converts price data into a Gaussian normal distribution.
- Values above +1.5: Overbought
- Values below -1.5: Oversold
- Sharp peaks/valleys signal reversals
- More responsive than RSI/Stochastic
"""

from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult
import math


class FisherTransformIndicator(Indicator):
    """Fisher Transform of price."""

    def __init__(self, period: int = 10):
        self.period = period

    def calculate(self, stock: Stock) -> IndicatorResult:
        highs = [bar.high for bar in stock.history]
        lows = [bar.low for bar in stock.history]

        if len(highs) < self.period + 1:
            return IndicatorResult(f"Fisher{self.period}", float("nan"))

        # Step 1: Normalize price to -1 to +1 range
        # Value = 2 * ((Close - Lowest Low) / (Highest High - Lowest Low)) - 1
        values = []
        for i in range(self.period, len(highs)):
            period_highs = highs[i - self.period + 1:i + 1]
            period_lows = lows[i - self.period + 1:i + 1]

            highest_high = max(period_highs)
            lowest_low = min(period_lows)
            close = stock.history[i].close

            if highest_high == lowest_low:
                norm = 0.0
            else:
                norm = 2.0 * ((close - lowest_low) / (highest_high - lowest_low)) - 1.0

            # Clamp to avoid extreme values
            norm = max(-0.999, min(0.999, norm))
            values.append(norm)

        if len(values) < 2:
            return IndicatorResult(f"Fisher{self.period}", float("nan"))

        # Step 2: Apply Fisher Transform
        # Fisher = 0.5 * ln((1 + value) / (1 - value))
        # Smoothed Fisher = EMA of Fisher
        fisher_values = []
        for v in values:
            fisher = 0.5 * math.log((1 + v) / (1 - v))
            fisher_values.append(fisher)

        # Apply simple smoothing (EMA-like)
        if len(fisher_values) < self.period:
            return IndicatorResult(f"Fisher{self.period}", float("nan"))

        smoothed = sum(fisher_values[:self.period]) / self.period
        multiplier = 2 / (self.period + 1)

        for f in fisher_values[self.period:]:
            smoothed = (f - smoothed) * multiplier + smoothed

        # Signal line: previous Fisher value
        signal = fisher_values[-1] if fisher_values else 0.0

        return IndicatorResult(
            f"Fisher{self.period}",
            smoothed
        )