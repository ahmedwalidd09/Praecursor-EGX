from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult
from math import isnan

class AVWAPIndicator(Indicator):
    """Anchored VWAP from most recent swing low (last 20 bars)."""

    def __init__(self, lookback: int = 20):
        self.lookback = lookback

    def calculate(self, stock: Stock) -> IndicatorResult:
        if len(stock.history) < self.lookback:
            return IndicatorResult("AVWAP_Distance_Pct", float("nan"))

        # Find the most recent swing low in the last `lookback` bars
        recent_bars = stock.history[-self.lookback:]
        
        lows = [bar.low for bar in recent_bars]
        min_low = min(lows)
        # Find index of the most recent occurrence of min_low
        swing_low_idx = len(recent_bars) - 1 - list(reversed(lows)).index(min_low)
        
        # Calculate VWAP anchored from that index
        anchored_bars = recent_bars[swing_low_idx:]
        
        cum_pv = 0.0
        cum_v = 0.0
        for bar in anchored_bars:
            vol = bar.volume or 0.0
            typ_price = (bar.high + bar.low + bar.close) / 3.0
            cum_pv += typ_price * vol
            cum_v += vol
            
        if cum_v == 0:
            return IndicatorResult("AVWAP_Distance_Pct", float("nan"))
            
        avwap = cum_pv / cum_v
        latest_close = stock.latest().close
        
        distance_pct = ((latest_close - avwap) / avwap) * 100.0 if avwap > 0 else float("nan")
        
        return IndicatorResult("AVWAP_Distance_Pct", distance_pct)
