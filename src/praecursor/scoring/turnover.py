from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult
import pandas as pd
import numpy as np

class AverageTurnoverIndicator(Indicator):
    """Calculates the 20-day average monetary turnover (Volume * Close)."""

    def __init__(self, period: int = 20):
        self.period = period

    def calculate(self, stock: Stock) -> IndicatorResult:
        prices = stock.prices
        if len(prices) < self.period:
            return IndicatorResult(f"AvgTurnover{self.period}", float("nan"))
            
        turnover = prices["volume"] * prices["close"]
        avg_turnover = turnover.rolling(window=self.period).mean().iloc[-1]
        
        return IndicatorResult(f"AvgTurnover{self.period}", float(avg_turnover))
