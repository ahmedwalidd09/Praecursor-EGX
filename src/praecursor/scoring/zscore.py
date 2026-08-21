import pandas as pd
import numpy as np

from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator as BaseIndicator
from praecursor.scoring.result import IndicatorResult


class RollingZScoreIndicator(BaseIndicator):

    def calculate(self, stock: Stock) -> IndicatorResult:
        # Implementing the abstract method from Indicator
        return self.analyze(stock)

    def analyze(self, stock: Stock) -> IndicatorResult:
        """
        Returns a dictionary with Z-Scores for RSI and Momentum.
        (Note: the type hint says IndicatorResult per instructions, but returns a dict)
        """
        closes = [bar.close for bar in stock.history]
        
        if len(closes) < 2:
            return {
                "RSI14_ZScore": float("nan"),
                "Momentum20_ZScore": float("nan")
            }

        df = pd.DataFrame({"close": closes})

        # Calculate 20-day Momentum (Price change over 20 days)
        df["mom"] = df["close"].diff(20)

        # Calculate 14-day RSI manually
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).fillna(0)
        loss = (-delta.where(delta < 0, 0)).fillna(0)

        # First averages are simple moving averages
        avg_gain = gain.rolling(window=14, min_periods=14).mean()
        avg_loss = loss.rolling(window=14, min_periods=14).mean()

        # For subsequent values, use Wilder's Smoothing (Exponential)
        # alpha = 1 / 14
        for i in range(14, len(df)):
            avg_gain.iloc[i] = (avg_gain.iloc[i - 1] * 13 + gain.iloc[i]) / 14
            avg_loss.iloc[i] = (avg_loss.iloc[i - 1] * 13 + loss.iloc[i]) / 14

        rs = avg_gain / avg_loss
        df["rsi"] = 100 - (100 / (1 + rs))

        # Calculate rolling 250-day mean and std
        df["rsi_mean"] = df["rsi"].rolling(window=250, min_periods=14).mean()
        df["rsi_std"] = df["rsi"].rolling(window=250, min_periods=14).std()

        df["mom_mean"] = df["mom"].rolling(window=250, min_periods=20).mean()
        df["mom_std"] = df["mom"].rolling(window=250, min_periods=20).std()

        # Calculate Z-Scores
        df["rsi_z"] = (df["rsi"] - df["rsi_mean"]) / df["rsi_std"]
        df["mom_z"] = (df["mom"] - df["mom_mean"]) / df["mom_std"]

        last_row = df.iloc[-1]
        
        rsi_z = float(last_row["rsi_z"]) if pd.notna(last_row["rsi_z"]) else float("nan")
        mom_z = float(last_row["mom_z"]) if pd.notna(last_row["mom_z"]) else float("nan")

        return IndicatorResult("RollingZScore", {
            "RSI14_ZScore": rsi_z,
            "Momentum20_ZScore": mom_z
        })
