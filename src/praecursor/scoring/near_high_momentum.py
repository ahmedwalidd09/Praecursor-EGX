import numpy as np
from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


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


class NearHighMomentumIndicator(Indicator):
    """
    Detects when a stock is near its 250-day closing high AND has strong momentum confirmation.
    'Coiled spring at the gate' pattern.
    """

    def calculate(self, stock: Stock) -> IndicatorResult:
        default_value = {
            "Close_High_250": 0.0,
            "Pct_From_High": 0.0,
            "Near_High": 0.0,
            "MACD_Hist_Positive": 0.0,
            "Mom5_Positive": 0.0,
            "Full_Confirmation": 0.0,
            "Partial_Confirmation": 0.0,
            "Very_Near": 0.0,
        }

        if not stock or not stock.history or len(stock.history) < 35:
            return IndicatorResult(name="NearHighMomentum", value=default_value)

        closes = [bar.close for bar in stock.history]

        # 1. 250-bar closing high (or all bars if fewer)
        last_250_closes = closes[-250:]
        close_high_250 = float(max(last_250_closes))
        latest_close = float(closes[-1])

        # 2. Distance from high
        if close_high_250 > 0:
            pct_from_high = float(((latest_close - close_high_250) / close_high_250) * 100)
        else:
            pct_from_high = 0.0

        # 3. Near high check (within 5% of high)
        near_high = 1.0 if pct_from_high >= -5.0 else 0.0

        # 4. MACD histogram calculation
        # Fast 12, Slow 26, Signal 9
        fast_ema = calculate_ema_series(closes, 12)
        slow_ema = calculate_ema_series(closes, 26)

        macd_series = [
            f - s
            for f, s in zip(fast_ema, slow_ema)
            if f is not None and s is not None
        ]

        if len(macd_series) < 9:
            return IndicatorResult(name="NearHighMomentum", value=default_value)

        signal_series = calculate_ema_series(macd_series, 9)
        latest_signal = signal_series[-1]
        latest_macd = macd_series[-1]

        if latest_signal is None or latest_macd is None:
            return IndicatorResult(name="NearHighMomentum", value=default_value)

        macd_histogram = float(latest_macd - latest_signal)
        macd_hist_positive = 1.0 if macd_histogram > 0 else 0.0

        # 5. 5-bar momentum
        close_5_bars_ago = float(closes[-6])
        mom5 = float(latest_close - close_5_bars_ago)
        mom5_positive = 1.0 if mom5 > 0 else 0.0

        # 6. Confirmation level checks
        full_confirmation = 1.0 if (near_high == 1.0 and macd_histogram > 0 and mom5 > 0) else 0.0
        partial_confirmation = 1.0 if (near_high == 1.0 and (macd_histogram > 0 or mom5 > 0)) else 0.0
        very_near = 1.0 if pct_from_high >= -2.0 else 0.0

        return IndicatorResult(
            name="NearHighMomentum",
            value={
                "Close_High_250": close_high_250,
                "Pct_From_High": pct_from_high,
                "Near_High": near_high,
                "MACD_Hist_Positive": macd_hist_positive,
                "Mom5_Positive": mom5_positive,
                "Full_Confirmation": full_confirmation,
                "Partial_Confirmation": partial_confirmation,
                "Very_Near": very_near,
            },
        )
