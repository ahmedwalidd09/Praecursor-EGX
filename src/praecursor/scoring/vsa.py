from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult

class VSANoDemandIndicator(Indicator):
    """Volume Spread Analysis: No Demand Bar."""
    
    def calculate(self, stock: Stock) -> IndicatorResult:
        if len(stock.history) < 20:
            return IndicatorResult("VSA_NoDemand", float("nan"))
            
        bars = stock.history
        latest = bars[-1]
        prev1 = bars[-2]
        prev2 = bars[-3]
        
        spread = latest.high - latest.low
        avg_spread = sum(b.high - b.low for b in bars[-20:]) / 20
        
        # 1. Narrow spread
        is_narrow = spread < avg_spread
        
        # 2. Close in middle/low
        close_pos = (latest.close - latest.low) / spread if spread > 0 else 0
        is_middle_low = close_pos < 0.5
        
        # 3. Lower volume than previous 2 bars
        is_low_vol = latest.volume < prev1.volume and latest.volume < prev2.volume
        
        is_up_bar = latest.close > prev1.close  # No demand is usually an up bar on low vol, but we'll stick to basic definition
        
        is_no_demand = is_narrow and is_middle_low and is_low_vol and is_up_bar
        
        return IndicatorResult("VSA_NoDemand", 1.0 if is_no_demand else 0.0)
