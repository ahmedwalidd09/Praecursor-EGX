from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult
import numpy as np


class VPOCIndicator(Indicator):
    """
    Volume Point of Control (VPOC).

    Calculates the price level with the highest traded volume over a
    rolling window (e.g. 100 days).

    Returns a dict with:
      - VPOC_Distance: normalised distance of close from VPOC price (positive = bullish)
      - VPOC_Price: raw VPOC price level
      - VPOC_Above: 1.0 if the VPOC is ABOVE the current close (i.e. resistance), else 0.0

    This allows next_day.py to perform a hard rejection when VPOC is acting as overhead resistance.
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
            idx = np.digitize(close, bin_edges) - 1
            if idx == self.bins:
                idx = self.bins - 1
            volume_profile[idx] += volume

        # Find the bin with the highest volume (VPOC)
        vpoc_idx = np.argmax(volume_profile)
        vpoc_price = (bin_edges[vpoc_idx] + bin_edges[vpoc_idx + 1]) / 2.0
        vpoc_volume = volume_profile[vpoc_idx]

        latest_close = stock.history[-1].close

        if vpoc_price == 0 or vpoc_volume == 0:
            return IndicatorResult("VPOC_Distance", 0.0)

        distance = (latest_close - vpoc_price) / vpoc_price
        vpoc_above = 1.0 if vpoc_price > latest_close else 0.0

        # High Volume Node (HVN) Resistance Rejection
        # Find all bins that have at least 60% of the VPOC volume
        hvn_threshold = vpoc_volume * 0.60
        overhead_hvn_detected = 0.0
        
        for i, vol in enumerate(volume_profile):
            if vol >= hvn_threshold:
                hvn_price = (bin_edges[i] + bin_edges[i+1]) / 2.0
                # If an HVN is directly above the current price (within 1% to 5% above)
                if latest_close < hvn_price and (hvn_price - latest_close) / latest_close <= 0.05:
                    overhead_hvn_detected = 1.0
                    break

        # Return a dict so callers can access both distance AND raw price
        return IndicatorResult("VPOC_Distance", {
            "VPOC_Distance": distance,
            "VPOC_Price": vpoc_price,
            "VPOC_Above": vpoc_above,
            "Overhead_HVN": overhead_hvn_detected
        })
