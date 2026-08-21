import numpy as np

from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class SqueezeIndicator(Indicator):
    """Detects Bollinger Band Squeezes - volatility compression and explosive breakouts."""

    def __init__(self, period: int = 20, lookback: int = 120):
        self.period = period
        self.lookback = lookback

    def calculate(self, stock: Stock) -> IndicatorResult:
        default_result = IndicatorResult(
            name="Squeeze",
            value={
                "BBW_Current": 0.0,
                "BBW_Min_120": 0.0,
                "Squeeze_Building": 0.0,
                "Squeeze_Fired": 0.0,
            },
        )

        if not stock.history:
            return default_result

        closes = np.array([bar.close for bar in stock.history], dtype=float)

        min_required_bars = self.lookback + self.period - 1
        if len(closes) < min_required_bars:
            return default_result

        recent_closes = closes[-min_required_bars:]

        bbw_values = []
        for i in range(self.lookback):
            window = recent_closes[i : i + self.period]
            middle = np.mean(window)
            std_dev = np.std(window)

            if middle == 0:
                bbw = 0.0
            else:
                bbw = float((4.0 * std_dev) / middle)

            bbw_values.append(bbw)

        bbw_array = np.array(bbw_values, dtype=float)
        current_bbw = float(bbw_array[-1])
        min_bbw_120 = float(np.min(bbw_array))

        # Check if current BBW is near 120-bar minimum (within 10% above it)
        squeeze_building = 1.0 if current_bbw <= min_bbw_120 * 1.1 else 0.0

        # Check if squeeze has FIRED:
        # 1. BBW was at its 120-bar minimum within the last 5 bars
        # 2. Current BBW is now expanding (current BBW > BBW from 3 bars ago)
        was_at_min_last_5 = np.isclose(np.min(bbw_array[-5:]), min_bbw_120)
        expanding = current_bbw > float(bbw_array[-4])

        squeeze_fired = 1.0 if (was_at_min_last_5 and expanding) else 0.0

        return IndicatorResult(
            name="Squeeze",
            value={
                "BBW_Current": current_bbw,
                "BBW_Min_120": min_bbw_120,
                "Squeeze_Building": squeeze_building,
                "Squeeze_Fired": squeeze_fired,
            },
        )
