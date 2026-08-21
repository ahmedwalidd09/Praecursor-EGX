"""VWAP Proximity Indicator (Upgrade #4).

Computes the distance between the latest close and the multi-day VWAP
(rolling N-bar Volume-Weighted Average Price).

Signals:
  - Positive distance: Price above VWAP — bullish; VWAP acts as support
  - Negative distance: Price below VWAP — bearish; VWAP acts as resistance
  - Very overextended (>5% above): caution; fade risk

Returns IndicatorResult named 'VWAP_Proximity' with value = pct distance.
"""

from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class VWAPProximityIndicator(Indicator):
    """Multi-day VWAP proximity: distance from VWAP as percent of VWAP."""

    def __init__(self, period: int = 20):
        self.period = period

    def calculate(self, stock: Stock) -> IndicatorResult:
        name = f"VWAP_Proximity{self.period}"
        history = stock.history

        if len(history) < self.period:
            return IndicatorResult(name, float("nan"))

        recent = history[-self.period:]
        total_pv = sum(bar.close * (bar.volume or 0) for bar in recent)
        total_v = sum(bar.volume or 0 for bar in recent)

        if total_v == 0:
            return IndicatorResult(name, float("nan"))

        vwap = total_pv / total_v
        latest_close = history[-1].close

        if vwap == 0:
            return IndicatorResult(name, float("nan"))

        distance_pct = ((latest_close - vwap) / vwap) * 100.0
        return IndicatorResult(name, distance_pct)
