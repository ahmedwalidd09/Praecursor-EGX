from typing import Dict, Any

from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator as BaseIndicator
from praecursor.scoring.result import IndicatorResult

class KalmanFilterIndicator(BaseIndicator):
    """
    1D Kalman Filter Indicator for smoothing stock prices and estimating trend.
    """

    def __init__(self, q: float = 1e-5, r: float = 1e-3, min_periods: int = 20):
        """
        Args:
            q: Process noise covariance
            r: Measurement noise covariance
            min_periods: Minimum number of periods required
        """
        self.q = q
        self.r = r
        self.min_periods = min_periods
        self.name = "KalmanFilter"

    def calculate(self, stock: Stock) -> IndicatorResult:
        return self.analyze(stock)

    def analyze(self, stock: Stock) -> IndicatorResult:
        closes = [bar.close for bar in stock.history]

        if len(closes) < self.min_periods:
            return IndicatorResult(
                self.name,
                {"KalmanPrice": float("nan"), "KalmanTrend": 0.0}
            )

        # Initialize
        x = closes[0]  # Initial state estimate
        p = 1.0        # Initial estimate covariance
        
        prev_x = x

        for z in closes:
            # Predict
            x_pred = x
            p_pred = p + self.q

            # Update
            k = p_pred / (p_pred + self.r)
            x = x_pred + k * (z - x_pred)
            p = (1 - k) * p_pred
            
            if z != closes[-1]:
                prev_x = x

        trend = 0.0
        if x > prev_x:
            trend = 1.0
        elif x < prev_x:
            trend = -1.0

        return IndicatorResult(
            self.name,
            {
                "KalmanPrice": x,
                "KalmanTrend": trend
            }
        )
