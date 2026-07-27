from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class AverageVolumeIndicator(Indicator):
    """Average trading volume over the latest period."""

    def __init__(self, period: int = 20):
        self.period = period

    def calculate(self, stock: Stock) -> IndicatorResult:
        volumes = [bar.volume for bar in stock.history]

        if len(volumes) < self.period:
            return IndicatorResult(f"AvgVolume{self.period}", float("nan"))

        average_volume = sum(volumes[-self.period:]) / self.period
        return IndicatorResult(f"AvgVolume{self.period}", average_volume)
