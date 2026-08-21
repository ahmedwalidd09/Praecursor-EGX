from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult

class EVMIndicator(Indicator):
    """Ease of Movement (EVM)."""
    
    def __init__(self, period: int = 14):
        self.period = period
        
    def calculate(self, stock: Stock) -> IndicatorResult:
        if len(stock.history) < self.period + 1:
            return IndicatorResult("EVM", float("nan"))
            
        evm_values = []
        bars = stock.history
        
        for i in range(1, len(bars)):
            curr = bars[i]
            prev = bars[i-1]
            
            mid_move = ((curr.high + curr.low) / 2) - ((prev.high + prev.low) / 2)
            box_ratio = (curr.volume / 10000.0) / (curr.high - curr.low) if (curr.high - curr.low) != 0 else float('inf')
            
            if box_ratio == float('inf') or box_ratio == 0:
                evm = 0.0
            else:
                evm = mid_move / box_ratio
                
            evm_values.append(evm)
            
        # Simple moving average of EVM
        if len(evm_values) < self.period:
            return IndicatorResult("EVM", float("nan"))
            
        smoothed_evm = sum(evm_values[-self.period:]) / self.period
        
        return IndicatorResult("EVM", smoothed_evm)
