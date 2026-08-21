"""Intraday Order Flow Imbalance Proxy (Batch 2 Upgrade #9).

Estimates buying vs selling pressure over a short window (e.g. 3 days) by 
calculating where the close occurred relative to the high-low range, 
weighted by volume.

Positive values mean strong buying pressure into the close.
Negative values mean heavy distribution into the close.
"""

from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult
import numpy as np


class OrderFlowImbalanceIndicator(Indicator):
    """Estimates short-term order flow imbalance."""

    def __init__(self, period: int = 3):
        self.period = period

    def calculate(self, stock: Stock) -> IndicatorResult:
        name = "OrderFlowImbalance"
        history = stock.history

        if len(history) < self.period:
            return IndicatorResult(name, 0.0)

        recent = history[-self.period:]
        imbalances = []

        for bar in recent:
            range_len = bar.high - bar.low
            if range_len == 0:
                imbalances.append(0.0)
            else:
                # Location of close relative to range [-1 to +1]
                # If close == high, location = 1.0
                # If close == low, location = -1.0
                # If close == mid, location = 0.0
                close_location = ((bar.close - bar.low) - (bar.high - bar.close)) / range_len
                imbalance = close_location * (bar.volume or 0)
                imbalances.append(imbalance)

        avg_daily_vol = np.mean([bar.volume or 0 for bar in recent])
        if avg_daily_vol == 0:
            return IndicatorResult(name, 0.0)

        # Sum of volume imbalances over the period, normalized by average daily volume
        total_imbalance = sum(imbalances)
        normalized_imbalance = total_imbalance / avg_daily_vol

        return IndicatorResult(name, normalized_imbalance)
