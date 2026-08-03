"""Average Directional Index (ADX) indicator.

ADX measures trend strength on a 0-100 scale regardless of trend direction.
- ADX < 20: market is ranging/consolidating (pre-breakout territory)
- ADX 20-40: developing trend
- ADX 40-60: strong trend
- ADX > 60: extremely strong trend
"""

from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class ADXIndicator(Indicator):
    """Calculate the Average Directional Index (ADX)."""

    def __init__(self, period: int = 14):
        self.period = period

    def calculate(self, stock: Stock) -> IndicatorResult:
        history = stock.history
        n = len(history)

        # ADX requires at least 2 * period + 1 bars
        if n < 2 * self.period + 1:
            return IndicatorResult(f"ADX{self.period}", float("nan"))

        # Step 1: Calculate +DM, -DM, and True Range for each bar
        plus_dm_list = []
        minus_dm_list = []
        tr_list = []

        for i in range(1, n):
            high = history[i].high
            low = history[i].low
            prev_high = history[i - 1].high
            prev_low = history[i - 1].low
            prev_close = history[i - 1].close

            up_move = high - prev_high
            down_move = prev_low - low

            plus_dm = up_move if up_move > down_move and up_move > 0 else 0.0
            minus_dm = down_move if down_move > up_move and down_move > 0 else 0.0

            true_range = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close),
            )

            plus_dm_list.append(plus_dm)
            minus_dm_list.append(minus_dm)
            tr_list.append(true_range)

        # Step 2: Smooth +DM, -DM, TR using Wilder's smoothing (first period is SMA)
        smoothed_plus_dm = sum(plus_dm_list[: self.period])
        smoothed_minus_dm = sum(minus_dm_list[: self.period])
        smoothed_tr = sum(tr_list[: self.period])

        dx_values = []

        for i in range(self.period, len(plus_dm_list)):
            smoothed_plus_dm = smoothed_plus_dm - (smoothed_plus_dm / self.period) + plus_dm_list[i]
            smoothed_minus_dm = smoothed_minus_dm - (smoothed_minus_dm / self.period) + minus_dm_list[i]
            smoothed_tr = smoothed_tr - (smoothed_tr / self.period) + tr_list[i]

            if smoothed_tr == 0:
                continue

            plus_di = 100.0 * smoothed_plus_dm / smoothed_tr
            minus_di = 100.0 * smoothed_minus_dm / smoothed_tr
            di_sum = plus_di + minus_di

            if di_sum == 0:
                dx_values.append(0.0)
            else:
                dx_values.append(100.0 * abs(plus_di - minus_di) / di_sum)

        if len(dx_values) < self.period:
            return IndicatorResult(f"ADX{self.period}", float("nan"))

        # Step 3: ADX is the smoothed average of DX
        adx = sum(dx_values[: self.period]) / self.period

        for i in range(self.period, len(dx_values)):
            adx = ((adx * (self.period - 1)) + dx_values[i]) / self.period

        return IndicatorResult(f"ADX{self.period}", adx)
