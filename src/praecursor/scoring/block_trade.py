"""Block Trade / Institutional Absorption Indicator (Upgrade #2).

Identifies days with an abnormally tight High-Low range (low volatility) 
but massive volume (e.g., >2x average). This indicates "absorption" or 
block trading by institutions. Breakouts immediately following absorption 
days have significantly higher win rates.
"""

from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult
import numpy as np


class BlockTradeIndicator(Indicator):
    """Detects recent institutional block trades/absorption."""

    def __init__(self, period: int = 20, lookback: int = 5, vol_multiplier: float = 2.0, range_percentile: float = 25.0):
        self.period = period
        self.lookback = lookback
        self.vol_multiplier = vol_multiplier
        self.range_percentile = range_percentile

    def calculate(self, stock: Stock) -> IndicatorResult:
        name = "RecentBlockTrade"
        history = stock.history

        if len(history) < self.period:
            return IndicatorResult(name, 0.0)

        recent = history[-self.period:]
        volumes = np.array([bar.volume or 0 for bar in recent])
        ranges = np.array([(bar.high - bar.low) / bar.low if bar.low > 0 else 0 for bar in recent])

        avg_volume = np.mean(volumes)
        if avg_volume == 0:
            return IndicatorResult(name, 0.0)

        # Range threshold: 25th percentile of the recent range (very tight)
        tight_range_threshold = np.percentile(ranges, self.range_percentile)
        
        # Check the last `lookback` days for absorption
        block_trade_detected = 0.0
        
        for i in range(-self.lookback, 0):
            bar = history[i]
            vol = bar.volume or 0
            rng = (bar.high - bar.low) / bar.low if bar.low > 0 else 0
            
            # Massive volume AND very tight range
            if vol > (avg_volume * self.vol_multiplier) and rng <= tight_range_threshold:
                block_trade_detected = 1.0
                break

        return IndicatorResult(name, block_trade_detected)
