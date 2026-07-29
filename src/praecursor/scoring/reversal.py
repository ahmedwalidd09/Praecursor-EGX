from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class RSIReboundIndicator(Indicator):
    """1 when RSI is recovering from a weak/oversold zone."""

    def __init__(self, period: int = 14):
        self.period = period

    def calculate(self, stock: Stock) -> IndicatorResult:
        closes = [bar.close for bar in stock.history]

        if len(closes) <= self.period + 1:
            return IndicatorResult("RSIRebound", float("nan"))

        previous_rsi = calculate_rsi(closes[:-1], self.period)
        latest_rsi = calculate_rsi(closes, self.period)

        if previous_rsi is None or latest_rsi is None:
            return IndicatorResult("RSIRebound", float("nan"))

        is_rebound = previous_rsi <= 45 and latest_rsi > previous_rsi and latest_rsi <= 60
        return IndicatorResult("RSIRebound", 1.0 if is_rebound else 0.0)


class EMA20ReclaimIndicator(Indicator):
    """1 when latest close reclaims EMA20 after being below it."""

    def calculate(self, stock: Stock) -> IndicatorResult:
        closes = [bar.close for bar in stock.history]

        if len(closes) < 21:
            return IndicatorResult("EMA20Reclaim", float("nan"))

        latest_ema20 = calculate_ema(closes, 20)
        previous_ema20 = calculate_ema(closes[:-1], 20)
        previous_close = closes[-2]
        latest_close = closes[-1]

        reclaimed = previous_close <= previous_ema20 and latest_close > latest_ema20
        return IndicatorResult("EMA20Reclaim", 1.0 if reclaimed else 0.0)


class MACDHistogramImprovementIndicator(Indicator):
    """Latest MACD histogram minus previous MACD histogram."""

    def calculate(self, stock: Stock) -> IndicatorResult:
        from praecursor.scoring.macd import calculate_macd_values

        closes = [bar.close for bar in stock.history]

        if len(closes) < 36:
            return IndicatorResult("MACDHistogramImprovement", float("nan"))

        latest_values = calculate_macd_values(closes)
        previous_values = calculate_macd_values(closes[:-1])

        if latest_values is None or previous_values is None:
            return IndicatorResult("MACDHistogramImprovement", float("nan"))

        improvement = latest_values.histogram - previous_values.histogram
        return IndicatorResult("MACDHistogramImprovement", improvement)


class VolumeSpikeFromWeaknessIndicator(Indicator):
    """1 when volume spikes after weak recent price momentum."""

    def __init__(self, volume_period: int = 20, weakness_period: int = 20):
        self.volume_period = volume_period
        self.weakness_period = weakness_period

    def calculate(self, stock: Stock) -> IndicatorResult:
        closes = [bar.close for bar in stock.history]
        volumes = [bar.volume for bar in stock.history]
        minimum_bars = max(self.volume_period + 1, self.weakness_period + 1)

        if len(closes) < minimum_bars or len(volumes) < minimum_bars:
            return IndicatorResult("VolumeSpikeFromWeakness", float("nan"))

        latest_volume = volumes[-1]
        average_volume = sum(volumes[-(self.volume_period + 1):-1]) / self.volume_period

        if average_volume <= 0:
            return IndicatorResult("VolumeSpikeFromWeakness", float("nan"))

        previous_close = closes[-(self.weakness_period + 1)]
        latest_close = closes[-1]

        if previous_close <= 0:
            return IndicatorResult("VolumeSpikeFromWeakness", float("nan"))

        momentum = ((latest_close / previous_close) - 1) * 100
        relative_volume = latest_volume / average_volume
        spike_from_weakness = momentum <= 3 and relative_volume >= 1.25

        return IndicatorResult("VolumeSpikeFromWeakness", 1.0 if spike_from_weakness else 0.0)


class Momentum5Indicator(Indicator):
    """Five-bar percentage momentum for short-term reversal detection."""

    def calculate(self, stock: Stock) -> IndicatorResult:
        closes = [bar.close for bar in stock.history]

        if len(closes) <= 5:
            return IndicatorResult("Momentum5", float("nan"))

        previous_close = closes[-6]
        latest_close = closes[-1]

        if previous_close <= 0:
            return IndicatorResult("Momentum5", float("nan"))

        momentum = ((latest_close / previous_close) - 1) * 100
        return IndicatorResult("Momentum5", momentum)


def calculate_ema(values: list[float], period: int) -> float:
    multiplier = 2 / (period + 1)
    ema = sum(values[:period]) / period

    for value in values[period:]:
        ema = (value - ema) * multiplier + ema

    return ema


def calculate_rsi(closes: list[float], period: int = 14) -> float | None:
    if len(closes) <= period:
        return None

    gains: list[float] = []
    losses: list[float] = []

    for index in range(1, len(closes)):
        change = closes[index] - closes[index - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for index in range(period, len(gains)):
        avg_gain = ((avg_gain * (period - 1)) + gains[index]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[index]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))
