import numpy as np
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class RollingZScoreIndicator(Indicator):
    def calculate(self, stock):
        return self.analyze(stock)

    def analyze(self, stock):
        closes = np.asarray([bar.close for bar in stock.history], dtype=float)
        rsi = np.full(len(closes), np.nan)
        if len(closes) >= 14:
            delta = np.diff(closes, prepend=closes[0])
            gains = np.maximum(delta, 0)
            losses = np.maximum(-delta, 0)
            avg_gain, avg_loss = gains[:14].mean(), losses[:14].mean()
            for i in range(13, len(closes)):
                if i >= 14:
                    avg_gain = (avg_gain * 13 + gains[i]) / 14
                    avg_loss = (avg_loss * 13 + losses[i]) / 14
                rsi[i] = 100 * avg_gain / (avg_gain + avg_loss) if avg_gain + avg_loss else np.nan
        momentum = closes[20:] - closes[:-20]

        def latest_z(values, minimum):
            window = values[-250:]
            valid = window[np.isfinite(window)]
            if len(valid) < minimum or not len(window) or not np.isfinite(window[-1]):
                return float("nan")
            std = valid.std(ddof=1)
            return float((window[-1] - valid.mean()) / std) if std > 0 else float("nan")

        return IndicatorResult("RollingZScore", {
            "RSI14_ZScore": latest_z(rsi, 14),
            "Momentum20_ZScore": latest_z(momentum, 20),
        })
