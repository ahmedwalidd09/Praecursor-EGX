from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class TrendStrengthIndicator(Indicator):
    """
    Simple EMA-structure trend strength score from 0 to 100.

    This is not ADX. It measures whether the close and EMAs are aligned in a
    bullish structure:
    - close > EMA20
    - EMA20 > EMA50
    - EMA50 > EMA200
    - close > EMA200
    """

    def calculate(self, stock: Stock) -> IndicatorResult:
        closes = [bar.close for bar in stock.history]

        if len(closes) < 200:
            return IndicatorResult("TrendStrength", float("nan"))

        latest_close = closes[-1]
        ema20 = self._calculate_ema(closes, 20)
        ema50 = self._calculate_ema(closes, 50)
        ema200 = self._calculate_ema(closes, 200)

        score = 0.0

        if latest_close > ema20:
            score += 25.0

        if ema20 > ema50:
            score += 25.0

        if ema50 > ema200:
            score += 25.0

        if latest_close > ema200:
            score += 25.0

        return IndicatorResult("TrendStrength", score)

    def _calculate_ema(self, values: list[float], period: int) -> float:
        multiplier = 2 / (period + 1)
        ema = sum(values[:period]) / period

        for value in values[period:]:
            ema = (value - ema) * multiplier + ema

        return ema
