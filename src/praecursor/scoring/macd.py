from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class MACDLineIndicator(Indicator):
    """MACD line: EMA(fast) - EMA(slow)."""

    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

    def calculate(self, stock: Stock) -> IndicatorResult:
        values = calculate_macd_values(
            [bar.close for bar in stock.history],
            self.fast_period,
            self.slow_period,
            self.signal_period,
        )

        if values is None:
            return IndicatorResult("MACD", float("nan"))

        return IndicatorResult("MACD", values.macd_line)


class MACDSignalIndicator(Indicator):
    """Signal line for MACD."""

    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

    def calculate(self, stock: Stock) -> IndicatorResult:
        values = calculate_macd_values(
            [bar.close for bar in stock.history],
            self.fast_period,
            self.slow_period,
            self.signal_period,
        )

        if values is None:
            return IndicatorResult("MACDSignal", float("nan"))

        return IndicatorResult("MACDSignal", values.signal_line)


class MACDHistogramIndicator(Indicator):
    """MACD histogram: MACD line - signal line."""

    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

    def calculate(self, stock: Stock) -> IndicatorResult:
        values = calculate_macd_values(
            [bar.close for bar in stock.history],
            self.fast_period,
            self.slow_period,
            self.signal_period,
        )

        if values is None:
            return IndicatorResult("MACDHistogram", float("nan"))

        return IndicatorResult("MACDHistogram", values.histogram)


class MACDValues:
    """Container for latest MACD values."""

    def __init__(self, macd_line: float, signal_line: float, histogram: float):
        self.macd_line = macd_line
        self.signal_line = signal_line
        self.histogram = histogram


def calculate_macd_values(
    closes: list[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> MACDValues | None:
    if len(closes) < slow_period + signal_period:
        return None

    fast_ema_series = calculate_ema_series(closes, fast_period)
    slow_ema_series = calculate_ema_series(closes, slow_period)

    macd_series = [
        fast_ema - slow_ema
        for fast_ema, slow_ema in zip(fast_ema_series, slow_ema_series)
        if fast_ema is not None and slow_ema is not None
    ]

    if len(macd_series) < signal_period:
        return None

    signal_series = calculate_ema_series(macd_series, signal_period)
    latest_signal = signal_series[-1]

    if latest_signal is None:
        return None

    latest_macd = macd_series[-1]
    histogram = latest_macd - latest_signal

    return MACDValues(
        macd_line=latest_macd,
        signal_line=latest_signal,
        histogram=histogram,
    )


def calculate_ema_series(values: list[float], period: int) -> list[float | None]:
    if len(values) < period:
        return [None for _ in values]

    multiplier = 2 / (period + 1)
    ema = sum(values[:period]) / period
    ema_series: list[float | None] = [None for _ in range(period - 1)]
    ema_series.append(ema)

    for value in values[period:]:
        ema = (value - ema) * multiplier + ema
        ema_series.append(ema)

    return ema_series
