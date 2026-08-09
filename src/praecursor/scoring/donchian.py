"""Donchian Channels indicator.

Donchian Channels use the highest high and lowest low over a period.
- Upper Band = Highest High over N periods
- Lower Band = Lowest Low over N periods
- Middle Band = (Upper + Lower) / 2
- Breakout above upper = Bullish
- Breakout below lower = Bearish
- Channel width = volatility measure
"""

from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class DonchianChannelsIndicator(Indicator):
    """Donchian Channels: highest high / lowest low over N periods."""

    def __init__(self, period: int = 20):
        self.period = period

    def calculate(self, stock: Stock) -> IndicatorResult:
        highs = [bar.high for bar in stock.history]
        lows = [bar.low for bar in stock.history]
        closes = [bar.close for bar in stock.history]

        if len(closes) <= self.period:
            return IndicatorResult(f"DC{self.period}_Position", float("nan"))

        upper_band = max(highs[-self.period:])
        lower_band = min(lows[-self.period:])
        middle_band = (upper_band + lower_band) / 2.0
        latest_close = closes[-1]

        # Position within channel: 1 = at upper, -1 = at lower, 0 = middle
        if upper_band == lower_band:
            position = 0.0
        else:
            position = 2.0 * (latest_close - middle_band) / (upper_band - lower_band)

        # Channel width as percentage
        channel_width_pct = ((upper_band - lower_band) / middle_band) * 100.0 if middle_band > 0 else 0.0

        # Breakout signals
        breakout_up = 1.0 if latest_close > upper_band else 0.0
        breakout_down = 1.0 if latest_close < lower_band else 0.0

        return IndicatorResult(
            f"DC{self.period}_Position",
            position
        )


class DonchianBreakoutIndicator(Indicator):
    """Donchian Channel breakout signals."""

    def __init__(self, period: int = 20):
        self.period = period

    def calculate(self, stock: Stock) -> IndicatorResult:
        highs = [bar.high for bar in stock.history]
        lows = [bar.low for bar in stock.history]
        closes = [bar.close for bar in stock.history]

        if len(closes) <= self.period + 1:
            return IndicatorResult(f"DCBreakout{self.period}", 0.0)

        prev_upper = max(highs[-self.period - 1:-1])
        prev_lower = min(lows[-self.period - 1:-1])
        latest_close = closes[-1]

        # Close above previous upper = bullish breakout
        # Close below previous lower = bearish breakout
        bullish_breakout = 1.0 if latest_close > prev_upper else 0.0
        bearish_breakout = 1.0 if latest_close < prev_lower else 0.0

        return IndicatorResult(
            f"DCBreakout{self.period}",
            1.0 if bullish_breakout else (-1.0 if bearish_breakout else 0.0)
        )