from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult
import pandas as pd
import numpy as np

class LimitUpIndicator(Indicator):
    """Detects if a stock closed at limit-up (approx 9.9% or 19.9% gain) relative to previous close."""

    def calculate(self, stock: Stock) -> IndicatorResult:
        prices = stock.prices
        if len(prices) < 2:
            return IndicatorResult("ClosedAtLimitUp", 0.0)
            
        latest_close = prices["close"].iloc[-1]
        prev_close = prices["close"].iloc[-2]
        
        if prev_close <= 0:
            return IndicatorResult("ClosedAtLimitUp", 0.0)
            
        daily_return = (latest_close - prev_close) / prev_close
        
        # Check for EGX 10% or 20% limit up 
        # (usually stocks close around +9.9% to +10.0%, or +19.9% to +20.0%)
        is_limit_up = (0.098 <= daily_return <= 0.105) or (0.198 <= daily_return <= 0.205)
        
        return IndicatorResult("ClosedAtLimitUp", 1.0 if is_limit_up else 0.0)
