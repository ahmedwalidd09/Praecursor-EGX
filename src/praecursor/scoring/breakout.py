from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class CloseBreakoutIndicator(Indicator):
    """
    1 when latest close breaks above the previous period's highest close.

    This intentionally uses closing prices instead of intraday highs because
    current public-source high/low quality is only medium.
    """

    def __init__(self, period: int):
        self.period = period

    def calculate(self, stock: Stock) -> IndicatorResult:
        closes = [bar.close for bar in stock.history]

        if len(closes) <= self.period:
            return IndicatorResult(f"Breakout{self.period}", float("nan"))

        latest_close = closes[-1]
        previous_highest_close = max(closes[-(self.period + 1):-1])
        breakout = 1.0 if latest_close > previous_highest_close else 0.0

        return IndicatorResult(f"Breakout{self.period}", breakout)


class CloseHighIndicator(Indicator):
    """Highest close over the latest period."""

    def __init__(self, period: int = 250):
        self.period = period

    def calculate(self, stock: Stock) -> IndicatorResult:
        closes = [bar.close for bar in stock.history]

        if len(closes) < self.period:
            return IndicatorResult(f"CloseHigh{self.period}", float("nan"))

        close_high = max(closes[-self.period:])
        return IndicatorResult(f"CloseHigh{self.period}", close_high)


class NearCloseHighIndicator(Indicator):
    """
    Percentage distance below the latest period's highest close.

    0 means latest close equals the period high. Negative means below the high.
    """

    def __init__(self, period: int = 250):
        self.period = period

    def calculate(self, stock: Stock) -> IndicatorResult:
        closes = [bar.close for bar in stock.history]

        if len(closes) < self.period:
            return IndicatorResult(f"NearCloseHigh{self.period}Percent", float("nan"))

        latest_close = closes[-1]
        close_high = max(closes[-self.period:])

        if close_high <= 0:
            return IndicatorResult(f"NearCloseHigh{self.period}Percent", float("nan"))

        distance_percent = ((latest_close / close_high) - 1) * 100
        return IndicatorResult(f"NearCloseHigh{self.period}Percent", distance_percent)


class VolumeConfirmedBreakoutIndicator(Indicator):
    """1 when latest close breaks out and relative volume confirms it."""

    def __init__(self, breakout_period: int = 20, volume_period: int = 20, minimum_relative_volume: float = 1.0):
        self.breakout_period = breakout_period
        self.volume_period = volume_period
        self.minimum_relative_volume = minimum_relative_volume

    def calculate(self, stock: Stock) -> IndicatorResult:
        closes = [bar.close for bar in stock.history]
        volumes = [bar.volume for bar in stock.history]

        minimum_bars = max(self.breakout_period + 1, self.volume_period + 1)

        if len(closes) < minimum_bars or len(volumes) < minimum_bars:
            return IndicatorResult("VolumeConfirmedBreakout", float("nan"))

        latest_close = closes[-1]
        previous_highest_close = max(closes[-(self.breakout_period + 1):-1])
        is_breakout = latest_close > previous_highest_close

        latest_volume = volumes[-1]
        average_volume = sum(volumes[-(self.volume_period + 1):-1]) / self.volume_period

        if average_volume <= 0:
            return IndicatorResult("VolumeConfirmedBreakout", float("nan"))

        relative_volume = latest_volume / average_volume
        confirmed = is_breakout and relative_volume >= self.minimum_relative_volume

        return IndicatorResult("VolumeConfirmedBreakout", 1.0 if confirmed else 0.0)
