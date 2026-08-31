from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class ClosingAggressionIndicator(Indicator):
    """
    Market-On-Close (MOC) and Closing Bar Aggression Detector.
    
    Quantifies whether institutional buyers aggressively swept the offer into the
    closing bell / closing auction, which is a major leading indicator of an explosive open.
    """

    def __init__(self, volume_lookback: int = 20):
        self.volume_lookback = volume_lookback

    def calculate(self, stock: Stock) -> IndicatorResult:
        if not stock.history or len(stock.history) < 5:
            return IndicatorResult("ClosingAggression", 0.0)

        bars = stock.history
        latest = bars[-1]
        rng = latest.high - latest.low

        if rng <= 0 or latest.high <= 0:
            return IndicatorResult("ClosingAggression", 0.0)

        # 1. Close Location Value (CLV): 0.0 (closed at low) to 1.0 (closed at high)
        clv = (latest.close - latest.low) / rng

        # 2. Close to High Proximity (e.g. 0.985 = within 1.5% of absolute day high)
        close_to_high = latest.close / latest.high

        # 3. Body-to-Range Dominance (Bullish Marubozu)
        body = latest.close - latest.open
        body_to_range = (body / rng) if body > 0 else 0.0

        # 4. Volume Confirmation
        vol_lookback_bars = bars[-min(len(bars), self.volume_lookback + 1):-1]
        avg_vol = (sum(b.volume for b in vol_lookback_bars) / len(vol_lookback_bars)) if vol_lookback_bars else latest.volume
        rel_vol = (latest.volume / avg_vol) if avg_vol > 0 else 1.0

        # Calculate Aggression Score (0.0 to 100.0)
        # Max score when CLV > 0.90, CloseToHigh > 0.98, Marubozu > 0.75, RelVol > 1.5x
        aggression_score = 0.0
        if clv >= 0.85:
            aggression_score += 40.0 * ((clv - 0.85) / 0.15)
        if close_to_high >= 0.97:
            aggression_score += 30.0 * ((close_to_high - 0.97) / 0.03)
        if body_to_range >= 0.60:
            aggression_score += 15.0
        if rel_vol >= 1.2:
            aggression_score += min(15.0, (rel_vol - 1.0) * 10.0)

        aggression_score = max(0.0, min(aggression_score, 100.0))
        return IndicatorResult("ClosingAggression", float(round(aggression_score, 2)))
