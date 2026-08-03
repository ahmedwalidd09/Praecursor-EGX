import math

from praecursor.core.stock import Stock
from praecursor.scoring.result import IndicatorResult
from praecursor.scoring.indicator import Indicator


class BollingerBandWidthIndicator(Indicator):
    """
    Calculates the Bollinger Band Width (BBW).
    BBW = (Upper Band - Lower Band) / Middle Band
    It is a powerful measure of volatility squeeze. Low BBW indicates a squeeze.
    """

    def __init__(self, period: int = 20, num_std: float = 2.0):
        self.period = period
        self.num_std = num_std
        self._name = f"BBW{period}"

    @property
    def name(self) -> str:
        return self._name

    def calculate(self, stock: Stock) -> IndicatorResult:
        if len(stock.history) < self.period:
            return IndicatorResult(self.name, float("nan"))

        closes = [bar.close for bar in stock.history[-self.period:]]
        sma = sum(closes) / self.period
        
        if sma == 0:
            return IndicatorResult(self.name, float("nan"))

        variance = sum((x - sma) ** 2 for x in closes) / self.period
        std_dev = math.sqrt(variance)

        upper_band = sma + (self.num_std * std_dev)
        lower_band = sma - (self.num_std * std_dev)
        
        bbw = (upper_band - lower_band) / sma

        return IndicatorResult(self.name, bbw)
