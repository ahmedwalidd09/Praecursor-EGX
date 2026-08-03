"""Stochastic RSI indicator.

StochRSI normalizes RSI into a 0-100 range relative to its own recent range.
This is more sensitive than plain RSI for detecting overbought/oversold conditions
within trending markets. Useful for timing entries during pullbacks in uptrends.

StochRSI = ((RSI - RSI_Low) / (RSI_High - RSI_Low)) * 100
"""

from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class StochasticRSIIndicator(Indicator):
    """Stochastic RSI: normalizes RSI within its own range over a lookback period."""

    def __init__(self, rsi_period: int = 14, stoch_period: int = 14):
        self.rsi_period = rsi_period
        self.stoch_period = stoch_period

    def calculate(self, stock: Stock) -> IndicatorResult:
        closes = [bar.close for bar in stock.history]

        # Need enough data for RSI calculation + stochastic lookback
        if len(closes) <= self.rsi_period + self.stoch_period:
            return IndicatorResult("StochRSI", float("nan"))

        # Step 1: Calculate RSI series
        rsi_series = self._compute_rsi_series(closes)

        if len(rsi_series) < self.stoch_period:
            return IndicatorResult("StochRSI", float("nan"))

        # Step 2: Apply stochastic formula to RSI values
        recent_rsi = rsi_series[-self.stoch_period:]
        rsi_high = max(recent_rsi)
        rsi_low = min(recent_rsi)

        rsi_range = rsi_high - rsi_low
        if rsi_range == 0:
            stoch_rsi = 100.0  # RSI has been flat (likely overbought or oversold)
        else:
            stoch_rsi = ((rsi_series[-1] - rsi_low) / rsi_range) * 100.0

        return IndicatorResult("StochRSI", stoch_rsi)

    def _compute_rsi_series(self, closes: list[float]) -> list[float]:
        """Compute RSI for each bar after the initial warm-up period."""
        gains = []
        losses = []

        for i in range(1, len(closes)):
            change = closes[i] - closes[i - 1]
            gains.append(max(change, 0))
            losses.append(max(-change, 0))

        if len(gains) < self.rsi_period:
            return []

        avg_gain = sum(gains[: self.rsi_period]) / self.rsi_period
        avg_loss = sum(losses[: self.rsi_period]) / self.rsi_period

        rsi_values = []

        # First RSI value
        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100 - (100 / (1 + rs)))

        # Subsequent RSI values using Wilder smoothing
        for i in range(self.rsi_period, len(gains)):
            avg_gain = ((avg_gain * (self.rsi_period - 1)) + gains[i]) / self.rsi_period
            avg_loss = ((avg_loss * (self.rsi_period - 1)) + losses[i]) / self.rsi_period

            if avg_loss == 0:
                rsi_values.append(100.0)
            else:
                rs = avg_gain / avg_loss
                rsi_values.append(100 - (100 / (1 + rs)))

        return rsi_values
