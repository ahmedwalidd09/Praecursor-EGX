"""Williams %R indicator.

Williams %R is a momentum oscillator that measures overbought/oversold levels.
- %R > -20: Overbought
- %R < -80: Oversold
- Formula: %R = (Highest High - Close) / (Highest High - Lowest Low) * -100
"""

from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class WilliamsRIndicator(Indicator):
    """Williams %R oscillator."""

    def __init__(self, period: int = 14):
        self.period = period

    def calculate(self, stock: Stock) -> IndicatorResult:
        highs = [bar.high for bar in stock.history]
        lows = [bar.low for bar in stock.history]
        closes = [bar.close for bar in stock.history]

        if len(closes) <= self.period:
            return IndicatorResult(f"WilliamsR{self.period}", float("nan"))

        # Calculate for the latest period
        recent_highs = highs[-self.period:]
        recent_lows = lows[-self.period:]
        latest_close = closes[-1]

        highest_high = max(recent_highs)
        lowest_low = min(recent_lows)

        if highest_high == lowest_low:
            return IndicatorResult(f"WilliamsR{self.period}", -50.0)  # Neutral

        williams_r = ((highest_high - latest_close) / (highest_high - lowest_low)) * -100.0

        return IndicatorResult(f"WilliamsR{self.period}", williams_r)