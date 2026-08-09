"""Money Flow Index (MFI) indicator.

MFI is a volume-weighted RSI that measures buying/selling pressure.
- MFI > 80: Overbought
- MFI < 20: Oversold
- Divergences between MFI and price signal potential reversals
"""

from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class MFIIndicator(Indicator):
    """Money Flow Index - volume-weighted RSI."""

    def __init__(self, period: int = 14):
        self.period = period

    def calculate(self, stock: Stock) -> IndicatorResult:
        highs = [bar.high for bar in stock.history]
        lows = [bar.low for bar in stock.history]
        closes = [bar.close for bar in stock.history]
        volumes = [bar.volume for bar in stock.history]

        if len(closes) <= self.period:
            return IndicatorResult(f"MFI{self.period}", float("nan"))

        # Typical Price = (High + Low + Close) / 3
        typical_prices = [(h + l + c) / 3.0 for h, l, c in zip(highs, lows, closes)]

        # Raw Money Flow = Typical Price * Volume
        raw_money_flow = [tp * v for tp, v in zip(typical_prices, volumes)]

        # Positive/Negative Money Flow
        positive_flow = []
        negative_flow = []

        for i in range(1, len(typical_prices)):
            if typical_prices[i] > typical_prices[i - 1]:
                positive_flow.append(raw_money_flow[i])
                negative_flow.append(0.0)
            elif typical_prices[i] < typical_prices[i - 1]:
                positive_flow.append(0.0)
                negative_flow.append(raw_money_flow[i])
            else:
                positive_flow.append(0.0)
                negative_flow.append(0.0)

        # Calculate MFI using Wilder smoothing
        if len(positive_flow) < self.period:
            return IndicatorResult(f"MFI{self.period}", float("nan"))

        pos_mf = sum(positive_flow[:self.period])
        neg_mf = sum(negative_flow[:self.period])

        for i in range(self.period, len(positive_flow)):
            pos_mf = ((pos_mf * (self.period - 1)) + positive_flow[i]) / self.period
            neg_mf = ((neg_mf * (self.period - 1)) + negative_flow[i]) / self.period

        if neg_mf == 0:
            mfi = 100.0
        else:
            money_ratio = pos_mf / neg_mf
            mfi = 100.0 - (100.0 / (1.0 + money_ratio))

        return IndicatorResult(f"MFI{self.period}", mfi)