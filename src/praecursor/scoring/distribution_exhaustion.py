"""Distribution Exhaustion Indicator (Batch 2 Upgrade #5).

Tracks cumulative volume over the last N days relative to a 90-day average volume baseline.
If the cumulative volume turns over excessively without the price advancing, it indicates
distribution (smart money selling into retail buying).
"""

from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult
import numpy as np


class DistributionExhaustionIndicator(Indicator):
    """Detects heavy volume turnover without price progress."""

    def __init__(self, short_period: int = 10, long_period: int = 90, turnover_threshold: float = 5.0):
        self.short_period = short_period
        self.long_period = long_period
        self.turnover_threshold = turnover_threshold

    def calculate(self, stock: Stock) -> IndicatorResult:
        name = "DistributionExhaustion"
        history = stock.history

        if len(history) < self.long_period:
            return IndicatorResult(name, 0.0)

        long_window = history[-self.long_period:]
        short_window = history[-self.short_period:]

        avg_daily_volume = np.mean([bar.volume or 0 for bar in long_window])
        if avg_daily_volume == 0:
            return IndicatorResult(name, 0.0)

        cumulative_recent_volume = sum(bar.volume or 0 for bar in short_window)
        
        # Calculate price progress in the short window
        start_price = short_window[0].open
        end_price = short_window[-1].close
        price_progress_pct = (end_price - start_price) / start_price if start_price > 0 else 0

        # Turnover Ratio = Total volume in 10 days / Average Daily Volume
        # A ratio of 10 means 10 days worth of average volume traded.
        # If it's vastly higher (e.g. > 25), huge turnover occurred.
        turnover_ratio = cumulative_recent_volume / avg_daily_volume

        exhaustion_flag = 0.0
        # If we turned over 10x the daily average in 10 days, that's just 1x relative volume.
        # So we look for e.g. 25x (which means 2.5x relative volume sustained for 10 days)
        # AND price didn't advance more than 3%
        if turnover_ratio > (self.short_period * 2.0) and price_progress_pct < 0.03:
            exhaustion_flag = 1.0

        return IndicatorResult(name, exhaustion_flag)
