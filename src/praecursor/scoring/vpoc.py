from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult
import numpy as np


class VPOCIndicator(Indicator):
    """
    Volume Point of Control (VPOC).
    
    Calculates the price level with the highest traded volume over a
    rolling window (e.g. 100 days). Returns the normalized distance
    of the current close from the VPOC.
    
    Positive score -> Close is above VPOC (Bullish, VPOC acts as support)
    Negative score -> Close is below VPOC (Bearish, VPOC acts as resistance)
    """

    def __init__(self, lookback: int = 100, bins: int = 50):
        self.lookback = lookback
        self.bins = bins

    def calculate(self, stock: Stock) -> IndicatorResult:
        if len(stock.history) < self.lookback:
            return IndicatorResult("VPOC_Distance", float("nan"))
            
        recent_bars = stock.history[-self.lookback:]
        closes = [bar.close for bar in recent_bars]
        volumes = [bar.volume for bar in recent_bars]
        
        # Bin the prices
        min_price = min(closes)
        max_price = max(closes)
        
        if min_price == max_price:
            return IndicatorResult("VPOC_Distance", 0.0)
            
        # Create bins
        bin_edges = np.linspace(min_price, max_price, self.bins + 1)
        volume_profile = np.zeros(self.bins)
        
        for close, volume in zip(closes, volumes):
            # Find the bin index for this close
            idx = np.digitize(close, bin_edges) - 1
            # Handle edge case where close == max_price
            if idx == self.bins:
                idx = self.bins - 1
            volume_profile[idx] += volume
            
        # Find the bin with the highest volume
        vpoc_idx = np.argmax(volume_profile)
        # VPOC price is the center of the winning bin
        vpoc_price = (bin_edges[vpoc_idx] + bin_edges[vpoc_idx + 1]) / 2.0
        
        latest_close = stock.history[-1].close
        
        if vpoc_price == 0:
            return IndicatorResult("VPOC_Distance", 0.0)
            
        distance = (latest_close - vpoc_price) / vpoc_price
        
        return IndicatorResult("VPOC_Distance", distance)
