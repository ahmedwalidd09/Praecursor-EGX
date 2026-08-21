import numpy as np
from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult

class LiquidityVacuumIndicator(Indicator):
    """
    Detects "air pockets" or liquidity vacuums in the order book based on historical volume profile.
    Calculates a score from 0.0 to 10.0 where 10.0 means there is zero historical volume in the 10% range above current price.
    """

    def __init__(self, lookback: int = 250, bins: int = 50):
        self.lookback = lookback
        self.bins = bins

    def calculate(self, stock: Stock) -> IndicatorResult:
        if len(stock.history) < self.lookback:
            return IndicatorResult("LiquidityVacuumScore", float("nan"))
            
        recent_bars = stock.history[-self.lookback:]
        closes = [bar.close for bar in recent_bars]
        volumes = [bar.volume for bar in recent_bars]
        
        min_price = min(closes)
        max_price = max(closes)
        
        if min_price == max_price:
            return IndicatorResult("LiquidityVacuumScore", 5.0)
            
        # Create bins
        bin_edges = np.linspace(min_price, max_price, self.bins + 1)
        volume_profile = np.zeros(self.bins)
        
        for close, volume in zip(closes, volumes):
            idx = np.digitize(close, bin_edges) - 1
            if idx == self.bins:
                idx = self.bins - 1
            volume_profile[idx] += volume
            
        vpoc_volume = np.max(volume_profile)
        if vpoc_volume == 0:
            return IndicatorResult("LiquidityVacuumScore", 0.0)
            
        latest_close = stock.history[-1].close
        upper_limit = latest_close * 1.10
        
        upper_range_volume = 0.0
        num_upper_bins = 0.0
        
        for i in range(self.bins):
            bin_low = bin_edges[i]
            bin_high = bin_edges[i+1]
            
            overlap_low = max(bin_low, latest_close)
            overlap_high = min(bin_high, upper_limit)
            
            if overlap_low < overlap_high:
                # Bin width could be 0 theoretically if max_price == min_price, but we checked that
                bin_width = bin_high - bin_low
                overlap_ratio = (overlap_high - overlap_low) / bin_width
                upper_range_volume += volume_profile[i] * overlap_ratio
                num_upper_bins += overlap_ratio
                
        if num_upper_bins == 0.0:
            # No historical volume above current close
            return IndicatorResult("LiquidityVacuumScore", 10.0)
            
        # Average volume per bin in the upper range
        avg_upper_volume = upper_range_volume / num_upper_bins
        
        # Compare to VPOC volume
        ratio = avg_upper_volume / vpoc_volume
        
        # Score from 0 to 10
        score = 10.0 * (1.0 - min(ratio, 1.0))
        
        return IndicatorResult("LiquidityVacuumScore", score)
