from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult
import pandas as pd


class MultiTimeframeIndicator(Indicator):
    """
    Calculates Weekly Trend Alignment (MTF).
    
    Resamples daily price bars to weekly closes, then calculates
    Weekly EMA20 and Weekly EMA50 to determine the macro trend structure.
    
    Returns 1.0 if Weekly Close > W_EMA20 > W_EMA50 (Macro Bullish)
    Returns -1.0 if Weekly Close < W_EMA20 < W_EMA50 (Macro Bearish)
    Returns 0.0 for ranging/neutral.
    """

    def calculate(self, stock: Stock) -> IndicatorResult:
        if len(stock.history) < 350: # Need ~50 weeks of data
            return IndicatorResult("MTF_Trend", float("nan"))
            
        dates = [bar.date for bar in stock.history]
        closes = [bar.close for bar in stock.history]
        
        # Build pandas series for easy resampling
        series = pd.Series(closes, index=pd.to_datetime(dates))
        weekly_closes = series.resample('W').last().dropna().values
        
        if len(weekly_closes) < 50:
            return IndicatorResult("MTF_Trend", float("nan"))
            
        latest_weekly_close = weekly_closes[-1]
        weekly_ema20 = self._calculate_ema(list(weekly_closes), 20)
        weekly_ema50 = self._calculate_ema(list(weekly_closes), 50)
        
        score = 0.0
        if latest_weekly_close > weekly_ema20 and weekly_ema20 > weekly_ema50:
            score = 1.0
        elif latest_weekly_close < weekly_ema20 and weekly_ema20 < weekly_ema50:
            score = -1.0
            
        return IndicatorResult("MTF_Trend", score)

    def _calculate_ema(self, values: list[float], period: int) -> float:
        multiplier = 2 / (period + 1)
        ema = sum(values[:period]) / period

        for value in values[period:]:
            ema = (value - ema) * multiplier + ema

        return ema
