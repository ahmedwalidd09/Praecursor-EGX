"""Ichimoku Cloud (Kumo) indicator.

Ichimoku Cloud components:
- Tenkan-sen (Conversion Line): (9-period high + 9-period low) / 2
- Kijun-sen (Base Line): (26-period high + 26-period low) / 2
- Senkou Span A (Leading Span A): (Tenkan + Kijun) / 2, plotted 26 periods ahead
- Senkou Span B (Leading Span B): (52-period high + 52-period low) / 2, plotted 26 periods ahead
- Chikou Span (Lagging Span): Close plotted 26 periods behind

Signals:
- Price above cloud = Bullish
- Price below cloud = Bearish
- Tenkan crosses above Kijun = Bullish (TK Cross)
- Tenkan crosses below Kijun = Bearish
- Cloud color (Span A > Span B = Green/Bullish, Span A < Span B = Red/Bearish)
"""

from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class IchimokuIndicator(Indicator):
    """Ichimoku Cloud indicator with key signals."""

    def __init__(self, tenkan_period: int = 9, kijun_period: int = 26, senkou_b_period: int = 52, displacement: int = 26):
        self.tenkan_period = tenkan_period
        self.kijun_period = kijun_period
        self.senkou_b_period = senkou_b_period
        self.displacement = displacement

    def calculate(self, stock: Stock) -> IndicatorResult:
        highs = [bar.high for bar in stock.history]
        lows = [bar.low for bar in stock.history]
        closes = [bar.close for bar in stock.history]

        n = len(closes)
        min_required = max(self.kijun_period, self.senkou_b_period) + self.displacement
        if n < min_required:
            return IndicatorResult("Ichimoku_CloudPosition", float("nan"))

        # Tenkan-sen (Conversion Line)
        tenkan_high = max(highs[-self.tenkan_period:])
        tenkan_low = min(lows[-self.tenkan_period:])
        tenkan = (tenkan_high + tenkan_low) / 2.0

        # Kijun-sen (Base Line)
        kijun_high = max(highs[-self.kijun_period:])
        kijun_low = min(lows[-self.kijun_period:])
        kijun = (kijun_high + kijun_low) / 2.0

        # Senkou Span A (Leading Span A) - current value
        senkou_a = (tenkan + kijun) / 2.0

        # Senkou Span B (Leading Span B) - current value
        senkou_b_high = max(highs[-self.senkou_b_period:])
        senkou_b_low = min(lows[-self.senkou_b_period:])
        senkou_b = (senkou_b_high + senkou_b_low) / 2.0

        latest_close = closes[-1]

        # Cloud position relative to price
        # Cloud is formed by Senkou Span A and B displaced forward
        # But we check current cloud (which was formed 26 periods ago)
        cloud_top = max(senkou_a, senkou_b)
        cloud_bottom = min(senkou_a, senkou_b)

        if latest_close > cloud_top:
            cloud_position = 1.0  # Above cloud (bullish)
        elif latest_close < cloud_bottom:
            cloud_position = -1.0  # Below cloud (bearish)
        else:
            cloud_position = 0.0  # Inside cloud (neutral/consolidation)

        # TK Cross (Tenkan vs Kijun)
        tk_cross = 1.0 if tenkan > kijun else (-1.0 if tenkan < kijun else 0.0)

        # Cloud color (Senkou A vs B)
        cloud_color = 1.0 if senkou_a > senkou_b else (-1.0 if senkou_a < senkou_b else 0.0)

        # Chikou Span (current close vs close 26 periods ago)
        chikou = 1.0 if closes[-1] > closes[-self.displacement - 1] else (-1.0 if closes[-1] < closes[-self.displacement - 1] else 0.0)

        # Composite Ichimoku score
        score = 0.0
        if cloud_position == 1.0:
            score += 30.0
        elif cloud_position == 0.0:
            score += 10.0
        else:
            score -= 20.0

        if tk_cross == 1.0:
            score += 25.0
        elif tk_cross == -1.0:
            score -= 20.0

        if cloud_color == 1.0:
            score += 15.0
        elif cloud_color == -1.0:
            score -= 10.0

        if chikou == 1.0:
            score += 15.0
        elif chikou == -1.0:
            score -= 10.0

        score = max(-100.0, min(100.0, score))

        return IndicatorResult(
            "Ichimoku_Score",
            score
        )