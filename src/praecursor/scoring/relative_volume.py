from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class RelativeVolumeIndicator(Indicator):
    """
    Latest volume divided by average volume over the previous period.

    The latest bar is excluded from the average so today's volume is compared
    against recent normal activity rather than partly against itself.
    """

    def __init__(self, period: int = 20):
        self.period = period

    def calculate(self, stock: Stock) -> IndicatorResult:
        volumes = [bar.volume for bar in stock.history]

        if len(volumes) <= self.period:
            return IndicatorResult(f"RelVolume{self.period}", float("nan"))

        latest_volume = volumes[-1]
        comparison_volumes = volumes[-(self.period + 1):-1]
        average_volume = sum(comparison_volumes) / self.period

        if average_volume <= 0:
            return IndicatorResult(f"RelVolume{self.period}", float("nan"))

        relative_volume = latest_volume / average_volume
        return IndicatorResult(f"RelVolume{self.period}", relative_volume)
