"""Elder Ray (Bull Power / Bear Power) indicator.

Bull Power = High - EMA
Bear Power = Low - EMA
- Bull Power > 0 and rising: Bulls in control
- Bear Power < 0 and falling: Bears in control
- Divergences signal reversals
"""

from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class ElderRayIndicator(Indicator):
    """Elder Ray: Bull Power and Bear Power."""

    def __init__(self, ema_period: int = 13):
        self.ema_period = ema_period

    def calculate(self, stock: Stock) -> IndicatorResult:
        closes = [bar.close for bar in stock.history]
        highs = [bar.high for bar in stock.history]
        lows = [bar.low for bar in stock.history]

        if len(closes) < self.ema_period:
            return IndicatorResult("ElderRay_BullPower", float("nan"))

        # Calculate EMA
        multiplier = 2 / (self.ema_period + 1)
        ema = sum(closes[:self.ema_period]) / self.ema_period

        for value in closes[self.ema_period:]:
            ema = (value - ema) * multiplier + ema

        latest_high = highs[-1]
        latest_low = lows[-1]

        bull_power = latest_high - ema
        bear_power = latest_low - ema

        # Normalize as percentage of price
        latest_close = closes[-1]
        if latest_close > 0:
            bull_power_pct = (bull_power / latest_close) * 100.0
            bear_power_pct = (bear_power / latest_close) * 100.0
        else:
            bull_power_pct = 0.0
            bear_power_pct = 0.0

        # Composite score: bullish if bull power positive & rising, bear power negative & falling
        score = 0.0
        if bull_power_pct > 0:
            score += 30.0
        if bear_power_pct < 0:
            score += 20.0  # Bear power negative is good (bears weak)
        elif bear_power_pct > 0:
            score -= 20.0  # Bear power positive is bad (bears strong)

        return IndicatorResult(
            "ElderRay_Score",
            score
        )