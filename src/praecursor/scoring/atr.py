from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class ATRIndicator(Indicator):
    """Average True Range over a lookback period."""

    def __init__(self, period: int = 14):
        self.period = period

    def calculate(self, stock: Stock) -> IndicatorResult:
        true_ranges = calculate_true_ranges(stock)

        if len(true_ranges) < self.period:
            return IndicatorResult(f"ATR{self.period}", float("nan"))

        atr = sum(true_ranges[: self.period]) / self.period

        for true_range in true_ranges[self.period :]:
            atr = ((atr * (self.period - 1)) + true_range) / self.period

        return IndicatorResult(f"ATR{self.period}", atr)


class ATRPercentIndicator(Indicator):
    """ATR as a percentage of latest close."""

    def __init__(self, period: int = 14):
        self.period = period

    def calculate(self, stock: Stock) -> IndicatorResult:
        atr_result = ATRIndicator(self.period).calculate(stock)
        latest_close = stock.latest().close

        if latest_close <= 0 or atr_result.value != atr_result.value:
            return IndicatorResult(f"ATRPercent{self.period}", float("nan"))

        atr_percent = (atr_result.value / latest_close) * 100
        return IndicatorResult(f"ATRPercent{self.period}", atr_percent)


def calculate_true_ranges(stock: Stock) -> list[float]:
    true_ranges: list[float] = []
    previous_close: float | None = None

    for bar in stock.history:
        high_low_range = bar.high - bar.low

        if previous_close is None:
            true_range = high_low_range
        else:
            true_range = max(
                high_low_range,
                abs(bar.high - previous_close),
                abs(bar.low - previous_close),
            )

        true_ranges.append(true_range)
        previous_close = bar.close

    return true_ranges
