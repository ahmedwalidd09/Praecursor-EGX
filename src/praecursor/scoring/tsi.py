from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult

class TSIIndicator(Indicator):
    """True Strength Index (TSI)."""
    
    def __init__(self, slow_period: int = 25, fast_period: int = 13):
        self.slow_period = slow_period
        self.fast_period = fast_period
        
    def calculate(self, stock: Stock) -> IndicatorResult:
        if len(stock.history) < self.slow_period + self.fast_period + 1:
            return IndicatorResult("TSI", float("nan"))
            
        closes = [bar.close for bar in stock.history]
        
        momentum = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        abs_momentum = [abs(m) for m in momentum]
        
        # Double smoothing momentum
        ema1_mom = self._calculate_ema_series(momentum, self.slow_period)
        valid_ema1_mom = [x for x in ema1_mom if x is not None]
        if len(valid_ema1_mom) < self.fast_period:
            return IndicatorResult("TSI", float("nan"))
        ema2_mom = self._calculate_ema_series(valid_ema1_mom, self.fast_period)
        
        # Double smoothing absolute momentum
        ema1_abs = self._calculate_ema_series(abs_momentum, self.slow_period)
        valid_ema1_abs = [x for x in ema1_abs if x is not None]
        ema2_abs = self._calculate_ema_series(valid_ema1_abs, self.fast_period)
        
        latest_mom = ema2_mom[-1]
        latest_abs = ema2_abs[-1]
        
        if latest_mom is None or latest_abs is None or latest_abs == 0:
            return IndicatorResult("TSI", float("nan"))
            
        tsi = 100 * (latest_mom / latest_abs)
        
        return IndicatorResult("TSI", tsi)

    def _calculate_ema_series(self, values: list[float], period: int) -> list[float | None]:
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
