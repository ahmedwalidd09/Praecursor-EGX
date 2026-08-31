from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class NR7CompressionIndicator(Indicator):
    """
    Multi-Timeframe Volatility Compression & NR7 (Narrowest Range of 7 days) Indicator.
    
    Explosive breakouts are preceded by extreme volatility contraction (coiling).
    Detects Toby Crabel / John Carter volatility compression setups.
    """

    def __init__(self, nr_period: int = 7):
        self.nr_period = nr_period

    def calculate(self, stock: Stock) -> IndicatorResult:
        if not stock.history or len(stock.history) < self.nr_period + 2:
            return IndicatorResult("NR7_Compression", 0.0)

        bars = stock.history
        
        # Calculate True Range for the last nr_period + 1 bars
        tr_list = []
        for i in range(len(bars) - self.nr_period, len(bars)):
            curr = bars[i]
            prev = bars[i - 1]
            tr = max(
                curr.high - curr.low,
                abs(curr.high - prev.close),
                abs(curr.low - prev.close)
            )
            tr_list.append(tr)

        if not tr_list:
            return IndicatorResult("NR7_Compression", 0.0)

        latest_tr = tr_list[-1]
        past_tr = tr_list[:-1]

        # 1. NR7: Today's True Range is strictly less than the previous (nr_period - 1) ranges
        is_nr7 = 1.0 if past_tr and latest_tr <= min(past_tr) else 0.0

        # 2. Inside Day
        latest = bars[-1]
        prev = bars[-2]
        is_inside_day = 1.0 if (latest.high <= prev.high and latest.low >= prev.low) else 0.0

        # 3. ID-NR4 (Inside Day + Narrowest Range in 4 days)
        past_4_tr = tr_list[-4:-1] if len(tr_list) >= 4 else past_tr
        is_nr4 = 1.0 if past_4_tr and latest_tr <= min(past_4_tr) else 0.0
        is_id_nr4 = 1.0 if (is_inside_day and is_nr4) else 0.0

        # 4. Volatility Coiling Score (0.0 to 100.0)
        score = 0.0
        if is_nr7:
            score += 50.0
        if is_inside_day:
            score += 25.0
        if is_id_nr4:
            score += 25.0

        # Trend filter bonus: if stock is in a macro uptrend (Close > EMA50 proxy), compression is primed bullishly
        if len(bars) >= 50:
            ema50_proxy = sum(b.close for b in bars[-50:]) / 50.0
            if latest.close > ema50_proxy:
                score = min(100.0, score * 1.15)

        return IndicatorResult("NR7_Compression", float(round(score, 2)))
