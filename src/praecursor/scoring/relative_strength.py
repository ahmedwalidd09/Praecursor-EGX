from typing import Any
import pandas as pd
from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult
from praecursor.scoring.regime import get_egx30_data

class RelativeStrengthIndicator(Indicator):
    """
    Calculates the Relative Strength of the stock vs the EGX30 benchmark.
    RS = Stock Close / Benchmark Close
    RS_ROC = (RS_today - RS_n_days_ago) / RS_n_days_ago
    """

    def __init__(self, period: int = 50):
        self.period = period
        self.name = f"RS_vs_EGX30_{period}"

    def calculate(self, stock: Stock) -> IndicatorResult:
        if len(stock.history) <= self.period:
            return IndicatorResult(self.name, float("nan"))
            
        egx30_df = get_egx30_data()
        if egx30_df.empty:
            return IndicatorResult(self.name, float("nan"))
            
        # Ensure we have date alignment
        current_date = stock.history[-1].date
        past_date = stock.history[-(self.period + 1)].date
        
        # Format dates exactly to match the yfinance index which has timezones
        current_date_ts = pd.Timestamp(current_date).tz_localize(egx30_df.index.tz) if egx30_df.index.tz else pd.Timestamp(current_date)
        past_date_ts = pd.Timestamp(past_date).tz_localize(egx30_df.index.tz) if egx30_df.index.tz else pd.Timestamp(past_date)
        
        try:
            # We use index matching or nearest if the dates don't perfectly align
            current_idx = egx30_df.index.get_indexer([current_date_ts], method="pad")[0]
            past_idx = egx30_df.index.get_indexer([past_date_ts], method="pad")[0]
            
            if current_idx == -1 or past_idx == -1:
                return IndicatorResult(self.name, float("nan"))
                
            bench_close_now = egx30_df.iloc[current_idx]["Close"]
            bench_close_past = egx30_df.iloc[past_idx]["Close"]
            
            stock_close_now = stock.history[-1].close
            stock_close_past = stock.history[-(self.period + 1)].close
            
            rs_now = stock_close_now / bench_close_now
            rs_past = stock_close_past / bench_close_past
            
            rs_roc = ((rs_now - rs_past) / rs_past) * 100.0
            return IndicatorResult(self.name, rs_roc)
        except Exception:
            return IndicatorResult(self.name, float("nan"))
