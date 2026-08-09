import sys

methods = '''
    def _score_ema_alignment(self, ema20: float, ema50: float, ema200: float, latest_close: float) -> ScoreComponent:
        max_score = 15.0
        if self._missing(ema20) or self._missing(ema50) or self._missing(ema200):
            return ScoreComponent("EMA Alignment", 0.0, max_score, "EMAs unavailable.")
        score = 0.0
        reasons = []
        if latest_close > ema20:
            score += 5.0
            reasons.append("Close > EMA20")
        if ema20 > ema50:
            score += 5.0
            reasons.append("EMA20 > EMA50")
        if ema50 > ema200:
            score += 5.0
            reasons.append("EMA50 > EMA200")
        return ScoreComponent("EMA Alignment", score, max_score, ", ".join(reasons) if reasons else "Poor alignment.")

    def _score_adx(self, adx14: float) -> ScoreComponent:
        max_score = 5.0
        if self._missing(adx14): return ScoreComponent("ADX", 0.0, max_score, "ADX unavailable.")
        if adx14 > 25: return ScoreComponent("ADX", max_score, max_score, "Strong trend (ADX > 25).")
        if adx14 > 20: return ScoreComponent("ADX", 2.0, max_score, "Developing trend.")
        return ScoreComponent("ADX", 0.0, max_score, "Weak trend.")

    def _score_supertrend(self, supertrend10: float, latest_close: float) -> ScoreComponent:
        max_score = 5.0
        if self._missing(supertrend10): return ScoreComponent("SuperTrend", 0.0, max_score, "SuperTrend unavailable.")
        if supertrend10 > 0: return ScoreComponent("SuperTrend", max_score, max_score, "Bullish SuperTrend.")
        return ScoreComponent("SuperTrend", 0.0, max_score, "Bearish SuperTrend.")

    def _score_ichimoku(self, ichimoku: float) -> ScoreComponent:
        max_score = 3.0
        if self._missing(ichimoku): return ScoreComponent("Ichimoku", 0.0, max_score, "Ichimoku unavailable.")
        return ScoreComponent("Ichimoku", min(ichimoku, max_score), max_score, f"Ichimoku score {ichimoku}.")

    def _score_elder_ray(self, elder_ray: float) -> ScoreComponent:
        max_score = 2.0
        if self._missing(elder_ray): return ScoreComponent("Elder Ray", 0.0, max_score, "Elder Ray unavailable.")
        return ScoreComponent("Elder Ray", min(max(elder_ray, 0.0), max_score), max_score, f"Elder Ray score {elder_ray}.")

    def _score_mfi14(self, mfi14: float) -> ScoreComponent:
        max_score = 2.0
        if self._missing(mfi14): return ScoreComponent("MFI", 0.0, max_score, "MFI unavailable.")
        if 50 <= mfi14 <= 80: return ScoreComponent("MFI", max_score, max_score, "Bullish MFI.")
        return ScoreComponent("MFI", 0.0, max_score, "Neutral/Bearish MFI.")

    def _score_williams_r(self, williams_r14: float) -> ScoreComponent:
        max_score = 1.0
        if self._missing(williams_r14): return ScoreComponent("Williams %R", 0.0, max_score, "Unavailable.")
        if williams_r14 > -50: return ScoreComponent("Williams %R", max_score, max_score, "Bullish.")
        return ScoreComponent("Williams %R", 0.0, max_score, "Bearish.")

    def _score_stoch_rsi(self, stoch_rsi: float) -> ScoreComponent:
        max_score = 1.0
        if self._missing(stoch_rsi): return ScoreComponent("StochRSI", 0.0, max_score, "Unavailable.")
        if stoch_rsi > 0: return ScoreComponent("StochRSI", max_score, max_score, "Bullish StochRSI cross.")
        return ScoreComponent("StochRSI", 0.0, max_score, "Bearish StochRSI.")

    def _score_fisher(self, fisher10: float) -> ScoreComponent:
        max_score = 1.0
        if self._missing(fisher10): return ScoreComponent("Fisher", 0.0, max_score, "Unavailable.")
        if fisher10 > 0: return ScoreComponent("Fisher", max_score, max_score, "Positive Fisher transform.")
        return ScoreComponent("Fisher", 0.0, max_score, "Negative Fisher.")

    def _score_momentum5(self, momentum5: float) -> ScoreComponent:
        max_score = 2.0
        if self._missing(momentum5): return ScoreComponent("Momentum5", 0.0, max_score, "Unavailable.")
        if momentum5 > 0: return ScoreComponent("Momentum5", max_score, max_score, "Positive short-term momentum.")
        return ScoreComponent("Momentum5", 0.0, max_score, "Negative short-term momentum.")

    def _score_roc10(self, roc10: float) -> ScoreComponent:
        max_score = 1.0
        if self._missing(roc10): return ScoreComponent("ROC10", 0.0, max_score, "Unavailable.")
        if roc10 > 0: return ScoreComponent("ROC10", max_score, max_score, "Positive ROC.")
        return ScoreComponent("ROC10", 0.0, max_score, "Negative ROC.")

    def _score_vwap_momentum(self, vwap_mom10: float) -> ScoreComponent:
        max_score = 2.0
        if self._missing(vwap_mom10): return ScoreComponent("VWAP Mom", 0.0, max_score, "Unavailable.")
        if vwap_mom10 > 0: return ScoreComponent("VWAP Mom", max_score, max_score, "Price above VWAP.")
        return ScoreComponent("VWAP Mom", 0.0, max_score, "Price below VWAP.")

    def _score_cmf(self, cmf20: float) -> ScoreComponent:
        max_score = 2.0
        if self._missing(cmf20): return ScoreComponent("CMF", 0.0, max_score, "Unavailable.")
        if cmf20 > 0: return ScoreComponent("CMF", max_score, max_score, "Positive money flow.")
        return ScoreComponent("CMF", 0.0, max_score, "Negative money flow.")

    def _score_force_index(self, force_index13: float) -> ScoreComponent:
        max_score = 1.0
        if self._missing(force_index13): return ScoreComponent("Force Index", 0.0, max_score, "Unavailable.")
        if force_index13 > 0: return ScoreComponent("Force Index", max_score, max_score, "Positive Force Index.")
        return ScoreComponent("Force Index", 0.0, max_score, "Negative Force Index.")

    def _score_turnover(self, avg_turnover20: float) -> ScoreComponent:
        max_score = 2.0
        if self._missing(avg_turnover20): return ScoreComponent("Turnover", 0.0, max_score, "Unavailable.")
        if avg_turnover20 > 1000000: return ScoreComponent("Turnover", max_score, max_score, "High turnover liquidity.")
        return ScoreComponent("Turnover", 0.0, max_score, "Low turnover.")

    def _score_donchian(self, dc_position: float, dc_breakout: float) -> ScoreComponent:
        max_score = 3.0
        if self._missing(dc_breakout): return ScoreComponent("Donchian", 0.0, max_score, "Unavailable.")
        if dc_breakout > 0: return ScoreComponent("Donchian", max_score, max_score, "Donchian Breakout.")
        return ScoreComponent("Donchian", 0.0, max_score, "No breakout.")

    def _score_keltner(self, kc_position: float, kc_squeeze: float) -> ScoreComponent:
        max_score = 3.0
        if self._missing(kc_position): return ScoreComponent("Keltner", 0.0, max_score, "Unavailable.")
        if kc_position > 50: return ScoreComponent("Keltner", max_score, max_score, "Bullish Keltner position.")
        return ScoreComponent("Keltner", 0.0, max_score, "Bearish Keltner.")

    def _score_bollinger_width(self, bbw20: float) -> ScoreComponent:
        max_score = 2.0
        if self._missing(bbw20): return ScoreComponent("BBW", 0.0, max_score, "Unavailable.")
        return ScoreComponent("BBW", max_score/2, max_score, "Normal BBW.")

    def _score_rsi_rebound(self, rsi_rebound: float) -> ScoreComponent:
        max_score = 2.0
        if self._missing(rsi_rebound): return ScoreComponent("RSI Rebound", 0.0, max_score, "Unavailable.")
        if rsi_rebound > 0: return ScoreComponent("RSI Rebound", max_score, max_score, "RSI Rebound detected.")
        return ScoreComponent("RSI Rebound", 0.0, max_score, "No RSI Rebound.")

    def _score_ema20_reclaim(self, ema20_reclaim: float) -> ScoreComponent:
        max_score = 3.0
        if self._missing(ema20_reclaim): return ScoreComponent("EMA20 Reclaim", 0.0, max_score, "Unavailable.")
        if ema20_reclaim > 0: return ScoreComponent("EMA20 Reclaim", max_score, max_score, "EMA20 Reclaim detected.")
        return ScoreComponent("EMA20 Reclaim", 0.0, max_score, "No EMA20 reclaim.")

    def _score_macd_improvement(self, macd_hist_improvement: float) -> ScoreComponent:
        max_score = 2.0
        if self._missing(macd_hist_improvement): return ScoreComponent("MACD Imp", 0.0, max_score, "Unavailable.")
        if macd_hist_improvement > 0: return ScoreComponent("MACD Imp", max_score, max_score, "MACD Histogram Improvement.")
        return ScoreComponent("MACD Imp", 0.0, max_score, "No MACD improvement.")

    def _score_volume_spike(self, volume_spike: float) -> ScoreComponent:
        max_score = 3.0
        if self._missing(volume_spike): return ScoreComponent("Vol Spike", 0.0, max_score, "Unavailable.")
        if volume_spike > 0: return ScoreComponent("Vol Spike", max_score, max_score, "Volume Spike detected.")
        return ScoreComponent("Vol Spike", 0.0, max_score, "No Volume Spike.")

    def _score_mtf_trend(self, mtf_trend: float) -> ScoreComponent:
        max_score = 3.0
        if self._missing(mtf_trend): return ScoreComponent("MTF Trend", 0.0, max_score, "Unavailable.")
        if mtf_trend > 0: return ScoreComponent("MTF Trend", max_score, max_score, "MTF Trend is bullish.")
        return ScoreComponent("MTF Trend", 0.0, max_score, "MTF Trend is not bullish.")

    def _score_vpoc(self, vpoc_distance: float) -> ScoreComponent:
        max_score = 2.0
        if self._missing(vpoc_distance): return ScoreComponent("VPOC", 0.0, max_score, "Unavailable.")
        if vpoc_distance > 0: return ScoreComponent("VPOC", max_score, max_score, "Price above VPOC.")
        return ScoreComponent("VPOC", 0.0, max_score, "Price below VPOC.")

    def _score_relative_strength(self, rs_egx30_50: float) -> ScoreComponent:
        max_score = 5.0
        if self._missing(rs_egx30_50): return ScoreComponent("Rel Strength", 0.0, max_score, "Unavailable.")
        if rs_egx30_50 > 0: return ScoreComponent("Rel Strength", max_score, max_score, "Outperforming EGX30.")
        return ScoreComponent("Rel Strength", 0.0, max_score, "Underperforming EGX30.")

    def _score_limit_up(self, limit_up: float) -> ScoreComponent:
        max_score = 5.0
        if self._missing(limit_up): return ScoreComponent("Limit Up", 0.0, max_score, "Unavailable.")
        if limit_up > 0: return ScoreComponent("Limit Up", max_score, max_score, "Closed at limit up.")
        return ScoreComponent("Limit Up", 0.0, max_score, "Did not close at limit up.")
'''

with open('src/praecursor/scoring/opportunity_score.py', 'a', encoding='utf-8') as f:
    f.write(methods)
