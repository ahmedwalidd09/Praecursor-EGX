import numpy as np

from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class VolatilityExpansionIndicator(Indicator):
    """Detects when a stock's ATR14 is expanding relative to its 20-bar average."""

    def calculate(self, stock: Stock) -> IndicatorResult:
        default_value = {
            "ATR_Expansion_Ratio": 0.0,
            "ATR_Expanding": 0.0,
            "ATR_Exploding": 0.0,
        }

        if not stock or not hasattr(stock, "history") or not stock.history:
            return IndicatorResult(name="VolatilityExpansion", value=default_value)

        bars = stock.history
        n_bars = len(bars)

        # Requires at least 14 bars for the initial ATR14, plus 19 more bars for 20 ATR14 values (minimum 33 bars)
        if n_bars < 33:
            return IndicatorResult(name="VolatilityExpansion", value=default_value)

        highs = np.array([bar.high for bar in bars], dtype=np.float64)
        lows = np.array([bar.low for bar in bars], dtype=np.float64)
        closes = np.array([bar.close for bar in bars], dtype=np.float64)

        # Calculate True Range (TR) for each bar
        tr = np.zeros(n_bars, dtype=np.float64)
        tr[0] = highs[0] - lows[0]

        hl = highs[1:] - lows[1:]
        h_pc = np.abs(highs[1:] - closes[:-1])
        l_pc = np.abs(lows[1:] - closes[:-1])

        tr[1:] = np.maximum(hl, np.maximum(h_pc, l_pc))

        # 14-bar simple moving average of TR
        atr14 = np.convolve(tr, np.ones(14) / 14.0, mode="valid")

        if len(atr14) < 20:
            return IndicatorResult(name="VolatilityExpansion", value=default_value)

        current_atr14 = float(atr14[-1])
        avg_atr14_20 = float(np.mean(atr14[-20:]))

        if avg_atr14_20 <= 0.0 or np.isnan(avg_atr14_20) or np.isnan(current_atr14):
            return IndicatorResult(name="VolatilityExpansion", value=default_value)

        ratio = float(current_atr14 / avg_atr14_20)
        expanding = 1.0 if ratio > 1.2 else 0.0
        exploding = 1.0 if ratio > 1.5 else 0.0

        return IndicatorResult(
            name="VolatilityExpansion",
            value={
                "ATR_Expansion_Ratio": ratio,
                "ATR_Expanding": expanding,
                "ATR_Exploding": exploding,
            },
        )
