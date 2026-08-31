from praecursor.core.stock import Stock
from praecursor.scoring.indicator import Indicator
from praecursor.scoring.result import IndicatorResult


class Analyzer:

    def __init__(self):
        self.indicators: list[Indicator] = []

    def add_indicator(self, indicator: Indicator):
        self.indicators.append(indicator)

    def analyze(self, stock: Stock):
        results = []

        for indicator in self.indicators:
            results.append(indicator.calculate(stock))

        closes = [b.close for b in stock.history] if stock.history else []

        # Momentum1: 1-bar return = (close[-1] - close[-2]) / close[-2] * 100 if len >= 2 else 0
        if len(closes) >= 2 and closes[-2] != 0:
            mom1 = (closes[-1] - closes[-2]) / closes[-2] * 100.0
        else:
            mom1 = 0.0
        results.append(IndicatorResult("Momentum1", mom1))

        # RSISlope3: RSI14 current minus RSI14 from 3 bars ago. If RSI history unavailable, 0.
        rsi_curr = float("nan")
        for r in results:
            if r.name == "RSI14":
                rsi_curr = r.value
                break
        rsi_3_ago = self._calc_rsi(closes[:-3], 14) if len(closes) > 3 else float("nan")

        if not (rsi_curr != rsi_curr) and not (rsi_3_ago != rsi_3_ago):
            rsi_slope3 = rsi_curr - rsi_3_ago
        else:
            rsi_slope3 = 0.0
        results.append(IndicatorResult("RSISlope3", rsi_slope3))

        # ConsecutiveGreen: Count backward from latest bar while close > previous close. Start at 0.
        consec = 0
        for i in range(len(closes) - 1, 0, -1):
            if closes[i] > closes[i - 1]:
                consec += 1
            else:
                break
        results.append(IndicatorResult("ConsecutiveGreen", float(consec)))

        # DayOfWeek: Latest bar's weekday as int (0=Mon, 6=Sun)
        if stock.history and hasattr(stock.history[-1], "date") and stock.history[-1].date is not None:
            dow = float(stock.history[-1].date.weekday())
        else:
            dow = 0.0
        results.append(IndicatorResult("DayOfWeek", dow))

        # Upgrade D: Intraday Order Flow Proxies
        vwap_div = 0.0
        eod_acc = 0.0
        if stock.intraday_history and stock.history:
            latest_date = stock.history[-1].date.date()
            # Filter intraday bars for the latest day
            day_bars = [b for b in stock.intraday_history if b.date.date() == latest_date]
            
            if day_bars:
                # VWAPDivergence15m
                typ_price_vol_sum = sum(((b.high + b.low + b.close) / 3.0) * b.volume for b in day_bars)
                vol_sum = sum(b.volume for b in day_bars)
                if vol_sum > 0:
                    vwap = typ_price_vol_sum / vol_sum
                    close_price = day_bars[-1].close
                    vwap_div = ((close_price - vwap) / vwap) * 100.0 if vwap > 0 else 0.0
                
                # EODAccumulation
                # Simple logic: compare volume in the last 2 bars (last 30m) to average volume of the day
                if len(day_bars) >= 4:
                    avg_vol = vol_sum / len(day_bars)
                    last_2_vol = sum(b.volume for b in day_bars[-2:])
                    # Normalized ratio
                    eod_acc = (last_2_vol / 2.0) / avg_vol if avg_vol > 0 else 0.0

        # Phase 3: VPOC
        vpoc_dist = 0.0
        if stock.intraday_history:
            from collections import defaultdict
            volume_by_price = defaultdict(float)
            for b in stock.intraday_history:
                price_level = round((b.high + b.low + b.close) / 3.0, 2)
                volume_by_price[price_level] += b.volume
            if volume_by_price:
                vpoc = max(volume_by_price.items(), key=lambda x: x[1])[0]
                latest_close = closes[-1] if closes else 0.0
                if vpoc > 0:
                    vpoc_dist = ((latest_close - vpoc) / vpoc) * 100.0
        results.append(IndicatorResult("VPOC_Distance", vpoc_dist))

        results.append(IndicatorResult("VWAPDivergence15m", vwap_div))
        results.append(IndicatorResult("EODAccumulation", eod_acc))

        return results

    @staticmethod
    def _calc_rsi(closes: list[float], period: int = 14) -> float:
        if len(closes) <= period:
            return float("nan")
        gains = []
        losses = []
        for i in range(1, len(closes)):
            change = closes[i] - closes[i - 1]
            gains.append(max(change, 0.0))
            losses.append(max(-change, 0.0))
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        for i in range(period, len(gains)):
            avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
            avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))