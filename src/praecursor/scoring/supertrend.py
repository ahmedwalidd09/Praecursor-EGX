"""SuperTrend indicator.

SuperTrend uses ATR to create a trailing stop line that flips direction.
- Price above SuperTrend = Uptrend (Bullish)
- Price below SuperTrend = Downtrend (Bearish)
- Line flips when price crosses it
"""

from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult
from praecursor.scoring.atr import calculate_true_ranges


class SuperTrendIndicator(Indicator):
    """SuperTrend: ATR-based trailing stop."""

    def __init__(self, period: int = 10, multiplier: float = 3.0):
        self.period = period
        self.multiplier = multiplier

    def calculate(self, stock: Stock) -> IndicatorResult:
        highs = [bar.high for bar in stock.history]
        lows = [bar.low for bar in stock.history]
        closes = [bar.close for bar in stock.history]

        if len(closes) < self.period + 1:
            return IndicatorResult(f"SuperTrend{self.period}", float("nan"))

        true_ranges = calculate_true_ranges(stock)
        if len(true_ranges) < self.period:
            return IndicatorResult(f"SuperTrend{self.period}", float("nan"))

        # Calculate ATR
        atr = sum(true_ranges[:self.period]) / self.period
        atr_values = [atr]
        for tr in true_ranges[self.period:]:
            atr = ((atr * (self.period - 1)) + tr) / self.period
            atr_values.append(atr)
            
        # Pad atr_values to match len(closes). The first self.period closes have no ATR.
        atr_values = [0.0] * self.period + atr_values

        # Calculate SuperTrend
        # Basic Upper Band = (High + Low) / 2 + multiplier * ATR
        # Basic Lower Band = (High + Low) / 2 - multiplier * ATR
        # Final Upper/Lower Bands with trend logic

        supertrend_values = []
        trend = 1  # 1 = uptrend, -1 = downtrend

        for i in range(len(closes)):
            if i == 0:
                # First bar
                basic_ub = (highs[i] + lows[i]) / 2.0 + self.multiplier * atr_values[0] if atr_values else 0
                basic_lb = (highs[i] + lows[i]) / 2.0 - self.multiplier * atr_values[0] if atr_values else 0
                final_ub = basic_ub
                final_lb = basic_lb
                supertrend = final_lb
                trend = 1
            else:
                basic_ub = (highs[i] + lows[i]) / 2.0 + self.multiplier * atr_values[i]
                basic_lb = (highs[i] + lows[i]) / 2.0 - self.multiplier * atr_values[i]

                # Final Upper Band
                if basic_ub < supertrend_values[-1] or closes[i - 1] > supertrend_values[-1]:
                    final_ub = basic_ub
                else:
                    final_ub = supertrend_values[-1]

                # Final Lower Band
                if basic_lb > supertrend_values[-1] or closes[i - 1] < supertrend_values[-1]:
                    final_lb = basic_lb
                else:
                    final_lb = supertrend_values[-1]

                # Determine trend
                if closes[i] <= final_ub and trend == 1:
                    trend = -1
                    supertrend = final_ub
                elif closes[i] >= final_lb and trend == -1:
                    trend = 1
                    supertrend = final_lb
                elif trend == 1:
                    supertrend = final_lb
                else:
                    supertrend = final_ub

            supertrend_values.append(supertrend)

        latest_close = closes[-1]
        latest_supertrend = supertrend_values[-1]

        # Distance from SuperTrend as percentage
        distance_pct = ((latest_close - latest_supertrend) / latest_close) * 100.0 if latest_close > 0 else 0.0

        # Trend direction
        trend_direction = 1 if latest_close > latest_supertrend else -1

        return IndicatorResult(
            f"SuperTrend{self.period}",
            distance_pct
        )