from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult

class VMACDSignalIndicator(Indicator):
    """Volume-Weighted MACD (V-MACD)."""
    
    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

    def calculate(self, stock: Stock) -> IndicatorResult:
        if len(stock.history) < self.slow_period + self.signal_period:
            return IndicatorResult("VMACD_Signal", float("nan"))
            
        closes = [bar.close for bar in stock.history]
        volumes = [bar.volume for bar in stock.history]
        
        cv_fast = [c * v for c, v in zip(closes, volumes)]
        cv_slow = [c * v for c, v in zip(closes, volumes)]
        
        ema_cv_fast = self._calculate_ema_series(cv_fast, self.fast_period)
        ema_vol_fast = self._calculate_ema_series(volumes, self.fast_period)
        
        ema_cv_slow = self._calculate_ema_series(cv_slow, self.slow_period)
        ema_vol_slow = self._calculate_ema_series(volumes, self.slow_period)
        
        v_macd_line = []
        for cv_f, v_f, cv_s, v_s in zip(ema_cv_fast, ema_vol_fast, ema_cv_slow, ema_vol_slow):
            if cv_f is not None and v_f is not None and cv_s is not None and v_s is not None and v_f > 0 and v_s > 0:
                vwema_fast = cv_f / v_f
                vwema_slow = cv_s / v_s
                v_macd_line.append(vwema_fast - vwema_slow)
            else:
                v_macd_line.append(None)
                
        # Calculate signal line (regular EMA of VMACD)
        valid_v_macd = [x for x in v_macd_line if x is not None]
        if len(valid_v_macd) < self.signal_period:
            return IndicatorResult("VMACD_Signal", float("nan"))
            
        signal_line_series = self._calculate_ema_series(valid_v_macd, self.signal_period)
        
        latest_macd = valid_v_macd[-1]
        latest_signal = signal_line_series[-1]
        
        if latest_macd is None or latest_signal is None:
            return IndicatorResult("VMACD_Signal", float("nan"))
            
        histogram = latest_macd - latest_signal
        
        return IndicatorResult("VMACD_Signal", histogram)

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
