from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class RSIIndicator(Indicator):

    def __init__(self, period: int = 14):
        self.period = period

    def calculate(self, stock: Stock) -> IndicatorResult:

        closes = [bar.close for bar in stock.history]

        if len(closes) <= self.period:
            return IndicatorResult(f"RSI{self.period}", float("nan"))

        gains = []
        losses = []

        for i in range(1, len(closes)):
            change = closes[i] - closes[i - 1]

            gains.append(max(change, 0))
            losses.append(max(-change, 0))

        avg_gain = sum(gains[:self.period]) / self.period
        avg_loss = sum(losses[:self.period]) / self.period

        for i in range(self.period, len(gains)):
            avg_gain = ((avg_gain * (self.period - 1)) + gains[i]) / self.period
            avg_loss = ((avg_loss * (self.period - 1)) + losses[i]) / self.period

        if avg_loss == 0:
            rsi = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))

        return IndicatorResult(f"RSI{self.period}", rsi)