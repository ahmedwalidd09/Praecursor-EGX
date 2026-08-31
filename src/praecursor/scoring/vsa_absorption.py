from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class VSAAbsorptionIndicator(Indicator):
    """
    Volume Spread Analysis (VSA) Institutional Supply Absorption Detector.
    
    Identifies 'Effort vs Result' anomalies where smart money absorbs selling pressure
    at key resistance pivots, clearing the way for a supply-free explosive markup.
    """

    def __init__(self, lookback: int = 20):
        self.lookback = lookback

    def calculate(self, stock: Stock) -> IndicatorResult:
        if not stock.history or len(stock.history) < self.lookback + 2:
            return IndicatorResult("VSA_Absorption", 0.0)

        bars = stock.history
        latest = bars[-1]
        prev = bars[-2]

        recent_bars = bars[-self.lookback - 1:-1]
        avg_vol = sum(b.volume for b in recent_bars) / len(recent_bars) if recent_bars else latest.volume
        avg_spread = sum(b.high - b.low for b in recent_bars) / len(recent_bars) if recent_bars else (latest.high - latest.low)

        curr_spread = latest.high - latest.low
        rel_vol = (latest.volume / avg_vol) if avg_vol > 0 else 1.0
        rel_spread = (curr_spread / avg_spread) if avg_spread > 0 else 1.0

        clv = (latest.close - latest.low) / curr_spread if curr_spread > 0 else 0.5

        absorption_score = 0.0

        # 1. Effort vs Result (Absorption): High Volume (>1.5x) + Controlled Spread (<1.3x) + Close in Upper Half (CLV > 0.6)
        if rel_vol >= 1.5 and rel_spread <= 1.4 and clv >= 0.60:
            absorption_score += 60.0 * min(1.5, rel_vol / 1.5)

        # 2. Absorption near 20-day Highs (Testing Resistance)
        high_20 = max(b.high for b in recent_bars[-20:])
        if latest.close >= high_20 * 0.96 and latest.close <= high_20 * 1.03:
            absorption_score += 25.0

        # 3. No-Supply Test: Low Volume Pullback (<0.7x vol) holding support
        is_no_supply = (rel_vol <= 0.70 and latest.close >= prev.close * 0.99 and latest.low >= prev.low)
        if is_no_supply and latest.close > (sum(b.close for b in recent_bars[-20:]) / 20.0):
            absorption_score += 40.0

        absorption_score = max(0.0, min(absorption_score, 100.0))
        return IndicatorResult("VSA_Absorption", float(round(absorption_score, 2)))
