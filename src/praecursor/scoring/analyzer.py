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

        # Phase 4: Hurst Exponent
        hurst_exponent = 0.5
        if len(closes) >= 100:
            import numpy as np
            lags = range(2, 20)
            diffs = [np.subtract(closes[lag:], closes[:-lag]) for lag in lags]
            # Replace 0s to avoid log issues
            tau = [np.sqrt(np.std(d)) if len(d)>0 else 1e-8 for d in diffs]
            # Clean tau to ensure > 0 before log
            tau = [t if t > 0 else 1e-8 for t in tau]
            poly = np.polyfit(np.log(lags), np.log(tau), 1)
            hurst_exponent = poly[0] * 2.0
            if np.isnan(hurst_exponent):
                hurst_exponent = 0.5
        results.append(IndicatorResult("hurst_exponent", hurst_exponent))

        # Phase 2: News Sentiment (Mocked)
        import random
        news_sentiment = random.uniform(-1.0, 1.0)
        results.append(IndicatorResult("news_sentiment", news_sentiment))
        
        # Phase 1: TFT Prob
        tft_prob = 0.0
        try:
            import torch
            from praecursor.ml.train_tft import TemporalTransformerPredictor
            from pathlib import Path
            model_path = Path(__file__).resolve().parents[3] / "models" / "tft_swing.pt"
            if model_path.exists() and stock.history and len(stock.history) >= 20:
                seq_bars = stock.history[-20:]
                import numpy as np
                closes_seq = np.array([b.close for b in seq_bars])
                opens = np.array([b.open for b in seq_bars])
                highs = np.array([b.high for b in seq_bars])
                lows = np.array([b.low for b in seq_bars])
                volumes = np.array([b.volume for b in seq_bars])
                max_p = max(highs.max(), 1e-5)
                max_v = max(volumes.max(), 1e-5)
                features = np.column_stack([opens / max_p, highs / max_p, lows / max_p, closes_seq / max_p, volumes / max_v])
                model = TemporalTransformerPredictor(input_size=5, d_model=64, nhead=4, num_layers=2)
                model.load_state_dict(torch.load(model_path))
                model.eval()
                with torch.no_grad():
                    out = model(torch.tensor([features], dtype=torch.float32))
                    tft_prob = torch.sigmoid(out).item()
        except Exception as e:
            pass
        results.append(IndicatorResult("tft_prob", tft_prob))

        # Phase 2: GNN Spillover Score
        gnn_score = 0.5
        try:
            import torch
            from praecursor.ml.train_gnn import MarketSpilloverGNN
            from pathlib import Path
            model_path = Path(__file__).resolve().parents[3] / "models" / "gnn_spillover.pt"
            if model_path.exists() and stock.history and len(stock.history) >= 20:
                # Mock a 1-node graph for the single stock inference to generate an embedding score
                import numpy as np
                model = MarketSpilloverGNN()
                model.load_state_dict(torch.load(model_path))
                model.eval()
                
                # Use recent bars to form node feature
                seq_bars = stock.history[-1:]
                closes = np.array([b.close for b in seq_bars])
                opens = np.array([b.open for b in seq_bars])
                highs = np.array([b.high for b in seq_bars])
                lows = np.array([b.low for b in seq_bars])
                volumes = np.array([b.volume for b in seq_bars])
                max_p = max(highs.max(), 1e-5)
                max_v = max(volumes.max(), 1e-5)
                
                features = np.column_stack([opens / max_p, highs / max_p, lows / max_p, closes / max_p, volumes / max_v])
                X = torch.tensor(features, dtype=torch.float32)
                A = torch.tensor([[1.0]], dtype=torch.float32) # Self-loop only for isolated inference
                
                with torch.no_grad():
                    out = model(A, X)
                    gnn_score = out.item()
        except Exception as e:
            pass
        results.append(IndicatorResult("gnn_spillover_score", gnn_score))

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