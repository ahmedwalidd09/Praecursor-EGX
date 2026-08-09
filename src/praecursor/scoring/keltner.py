"""Keltner Channels indicator.

Keltner Channels use ATR to set channel width around an EMA.
- Upper Band = EMA + (multiplier * ATR)
- Lower Band = EMA - (multiplier * ATR)
- Squeeze: When bands narrow significantly (volatility contraction)
- Breakout: Close crossing above upper band (bullish) or below lower band (bearish)
"""

from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult
from praecursor.scoring.atr import calculate_true_ranges


class KeltnerChannelsIndicator(Indicator):
    """Keltner Channels: EMA-based channels with ATR width."""

    def __init__(self, period: int = 20, multiplier: float = 2.0):
        self.period = period
        self.multiplier = multiplier

    def calculate(self, stock: Stock) -> IndicatorResult:
        closes = [bar.close for bar in stock.history]
        highs = [bar.high for bar in stock.history]
        lows = [bar.low for bar in stock.history]

        if len(closes) < self.period + 1:
            return IndicatorResult(f"KC{self.period}_Position", float("nan"))

        # Calculate EMA
        ema = self._calculate_ema(closes, self.period)

        # Calculate ATR
        true_ranges = calculate_true_ranges(stock)
        if len(true_ranges) < self.period:
            return IndicatorResult(f"KC{self.period}_Position", float("nan"))

        atr = sum(true_ranges[: self.period]) / self.period
        for tr in true_ranges[self.period:]:
            atr = ((atr * (self.period - 1)) + tr) / self.period

        # Calculate bands
        upper_band = ema + (self.multiplier * atr)
        lower_band = ema - (self.multiplier * atr)
        latest_close = closes[-1]

        # Position within channels: 1 = above upper, 0 = below lower, 0.5 = middle
        if upper_band == lower_band:
            position = 0.5
        else:
            position = (latest_close - lower_band) / (upper_band - lower_band)

        # Squeeze detection: channel width relative to price
        channel_width_pct = ((upper_band - lower_band) / ema) * 100 if ema > 0 else 0

        # Return position as main value, channel width as extra info
        return IndicatorResult(
            f"KC{self.period}_Position",
            position
        )

    def _calculate_ema(self, values: list[float], period: int) -> float:
        multiplier = 2 / (period + 1)
        ema = sum(values[:period]) / period

        for value in values[period:]:
            ema = (value - ema) * multiplier + ema

        return ema


class KeltnerSqueezeIndicator(Indicator):
    """Detects Keltner Channel squeeze (volatility contraction)."""

    def __init__(self, period: int = 20, multiplier: float = 2.0, lookback: int = 50):
        self.period = period
        self.multiplier = multiplier
        self.lookback = lookback

    def calculate(self, stock: Stock) -> IndicatorResult:
        closes = [bar.close for bar in stock.history]
        highs = [bar.high for bar in stock.history]
        lows = [bar.low for bar in stock.history]

        if len(closes) < self.period + self.lookback:
            return IndicatorResult(f"KCSqueeze{self.period}", float("nan"))

        true_ranges = calculate_true_ranges(stock)

        channel_widths = []
        for i in range(self.period, len(closes) + 1):
            # Calculate EMA for this point
            ema = self._calculate_ema(closes[:i], self.period)
            # Calculate ATR for this point
            atr_values = true_ranges[:i]
            if len(atr_values) < self.period:
                continue
            atr = sum(atr_values[: self.period]) / self.period
            for tr in atr_values[self.period:]:
                atr = ((atr * (self.period - 1)) + tr) / self.period

            upper = ema + (self.multiplier * atr)
            lower = ema - (self.multiplier * atr)
            width_pct = ((upper - lower) / ema) * 100 if ema > 0 else 0
            channel_widths.append(width_pct)

        if len(channel_widths) < self.lookback:
            return IndicatorResult(f"KCSqueeze{self.period}", float("nan"))

        # Current width vs recent average
        current_width = channel_widths[-1]
        recent_avg_width = sum(channel_widths[-self.lookback:]) / self.lookback
        min_width = min(channel_widths[-self.lookback:])

        # Squeeze ratio: current / average (lower = tighter squeeze)
        squeeze_ratio = current_width / recent_avg_width if recent_avg_width > 0 else 1.0
        # Also check if at historical minimum
        at_minimum = 1.0 if current_width <= min_width * 1.05 else 0.0

        return IndicatorResult(
            f"KCSqueeze{self.period}",
            squeeze_ratio
        )

    def _calculate_ema(self, values: list[float], period: int) -> float:
        multiplier = 2 / (period + 1)
        ema = sum(values[:period]) / period

        for value in values[period:]:
            ema = (value - ema) * multiplier + ema

        return ema