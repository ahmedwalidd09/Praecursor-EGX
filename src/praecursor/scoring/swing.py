from dataclasses import dataclass
from math import isnan
from pathlib import Path
import logging

try:
    import pandas as pd
    import numpy as np
    import xgboost as xgb
    HAS_ML = True
except ImportError:
    HAS_ML = False
    np = None

from praecursor.scoring.opportunity_score import OpportunityScore
from praecursor.scoring.position_sizing import calculate_position_size

_MAE_MODEL = None
_TFT_MODEL = None
_TORCH_AVAILABLE = False

try:
    import torch
    import torch.nn as nn
    _TORCH_AVAILABLE = True
    from praecursor.ml.train_tft import TemporalTransformerPredictor
except ImportError:
    pass


def _get_tft_model():
    global _TFT_MODEL
    if _TFT_MODEL is None and _TORCH_AVAILABLE:
        try:
            model_path = Path(__file__).resolve().parents[3] / "models" / "tft_swing.pt"
            if model_path.exists():
                _TFT_MODEL = TemporalTransformerPredictor(input_size=5, d_model=64, nhead=4, num_layers=2)
                _TFT_MODEL.load_state_dict(torch.load(str(model_path)))
                _TFT_MODEL.eval()
            else:
                _TFT_MODEL = False
        except Exception as e:
            logger.warning(f"Failed to load TFT model: {e}")
            _TFT_MODEL = False
    return _TFT_MODEL if _TFT_MODEL is not False else None

def _get_mae_model():
    global _MAE_MODEL
    if _MAE_MODEL is None:
        try:
            import lightgbm as lgb
            model_path = Path(__file__).resolve().parents[3] / "models" / "lightgbm_mae.txt"
            if model_path.exists():
                _MAE_MODEL = lgb.Booster(model_file=str(model_path))
            else:
                _MAE_MODEL = False
        except Exception:
            _MAE_MODEL = False
    return _MAE_MODEL if _MAE_MODEL is not False else None

logger = logging.getLogger(__name__)

_SWING_MODEL = None
_SWING_LGB_MODEL = None

def _get_swing_model():
    global _SWING_MODEL
    if not HAS_ML:
        return None
        
    if _SWING_MODEL is None:
        try:
            model_path = Path(__file__).resolve().parents[3] / "models" / "xgboost_swing.json"
            if model_path.exists():
                _SWING_MODEL = xgb.XGBClassifier()
                _SWING_MODEL.load_model(str(model_path))
            else:
                _SWING_MODEL = False
        except Exception as e:
            logger.error(f"Failed to load swing ML model: {e}")
            _SWING_MODEL = False
            
    return _SWING_MODEL if _SWING_MODEL is not False else None

def _get_swing_lgb_model():
    global _SWING_LGB_MODEL
    if _SWING_LGB_MODEL is None:
        try:
            import lightgbm as lgb
            model_path = Path(__file__).resolve().parents[3] / "models" / "lightgbm_swing.txt"
            if model_path.exists():
                _SWING_LGB_MODEL = lgb.Booster(model_file=str(model_path))
            else:
                _SWING_LGB_MODEL = False
        except Exception:
            _SWING_LGB_MODEL = False
    return _SWING_LGB_MODEL if _SWING_LGB_MODEL is not False else None


@dataclass(frozen=True)
class SwingPrediction:
    """10-20 bar swing opportunity assessment."""

    score: float
    label: str
    reasons: list[str]
    latest_close: float = 0.0
    target_price: float = 0.0
    stop_loss_price: float = 0.0
    position_size: float = 0.0
    max_risk: float = 0.0
    dynamic_stop: bool = False

    @property
    def reasons_text(self) -> str:
        return "; ".join(self.reasons)


def calculate_swing_prediction(
    opportunity_score: OpportunityScore,
    consensus_accepted: bool = True,
    consensus_confidence: float = 40.0,
    data_quality_score: float = 100.0,
) -> SwingPrediction:
    values = opportunity_score.indicator_values
    
    model = _get_swing_model()
    
    if model is not None:
        features = [
            "RSI14", "RelVolume20", "MACDHistogram", "Momentum20", 
            "Breakout20", "Breakout50", "RSIRebound", "EMA20Reclaim", 
            "MACDHistogramImprovement", "VolumeSpikeFromWeakness", "Momentum5", "BBW20",
            "MTF_Trend", "VPOC_Distance", "ADX14", "ROC10", "StochRSI", "VWAPMom10"
        ]
        
        csv_features = [
            "rsi14", "rel_volume20", "macd_histogram", "momentum20", "breakout20", "breakout50",
            "rsi_rebound", "ema20_reclaim", "macd_histogram_improvement", "volume_spike_from_weakness", "momentum5", "bbw20",
            "mtf_trend", "vpoc_distance", "adx14", "roc10", "stoch_rsi", "vwap_mom10"
        ]
        row_data = {csv_name: values.get(orig_name, 0.0) for csv_name, orig_name in zip(csv_features, features)}
        for k, v in row_data.items():
            if v != v:
                row_data[k] = 0.0
        df = pd.DataFrame([row_data])
        
        old_features = [
            "rsi14", "rel_volume20", "macd_histogram", "momentum20", "breakout20", "breakout50",
            "rsi_rebound", "ema20_reclaim", "macd_histogram_improvement", "volume_spike_from_weakness", "momentum5", "bbw20",
            "mtf_trend", "vpoc_distance"
        ]
        try:
            prob = model.predict_proba(df[old_features])[0][1]
        except Exception:
            prob = 0.0
        
        # Ensemble with LightGBM if available
        lgb_model = _get_swing_lgb_model()
        if lgb_model is not None:
            try:
                lgb_prob = lgb_model.predict(df)[0]
                prob = 0.6 * prob + 0.4 * lgb_prob
            except Exception:
                pass
                
        # Ensemble with PyTorch TFT if available
        tft_model = _get_tft_model()
        stock_obj = getattr(opportunity_score, "stock", None)
        if tft_model is not None and stock_obj is not None and np is not None:
            try:
                history = stock_obj.history
                if len(history) >= 20:
                    seq_bars = history[-20:]
                    closes = np.array([b.close for b in seq_bars])
                    opens = np.array([b.open for b in seq_bars])
                    highs = np.array([b.high for b in seq_bars])
                    lows = np.array([b.low for b in seq_bars])
                    volumes = np.array([b.volume for b in seq_bars])
                    
                    max_p = max(highs.max(), 1e-5)
                    max_v = max(volumes.max(), 1e-5)
                    
                    features = np.column_stack([
                        opens / max_p,
                        highs / max_p,
                        lows / max_p,
                        closes / max_p,
                        volumes / max_v
                    ])
                    
                    x_tensor = torch.tensor(features, dtype=torch.float32).unsqueeze(0)
                    with torch.no_grad():
                        out = tft_model(x_tensor)
                        tft_prob = torch.sigmoid(out).item()
                        
                    # Final ensemble: 50% Tree based, 50% Deep Learning TFT
                    prob = (prob * 0.5) + (tft_prob * 0.5)
                    reasons.append(f"Deep Learning (TFT) consensus applied")
            except Exception as e:
                logger.warning(f"Failed PyTorch inference: {e}")
        
        score = prob * 100.0
        
        reasons = [f"AI Probability: {score:.1f}%"]
        if score >= 50:
            reasons.append("ML model predicts a positive 20-day return")
            
        if not consensus_accepted:
            score -= 20.0
            reasons.append("latest close consensus is not accepted")

        if data_quality_score < 60:
            score -= 10.0
            reasons.append("data quality is low")
            
        score = max(0.0, min(score, 100.0))
        label = _label(score, 0.0, 0.0, consensus_accepted, using_ml=True, opp_score=opportunity_score.total_score)
            
    else:
        trend_score, trend_reasons = _trend_continuation_score(values)
        reversal_score, reversal_reasons = _swing_reversal_score(values)
        quality_adjustment, quality_reasons = _quality_adjustment(
            consensus_accepted,
            consensus_confidence,
            data_quality_score,
        )

        raw_score = max(trend_score, reversal_score) + quality_adjustment
        score = max(0.0, min(raw_score, 100.0))
        label = _label(score, trend_score, reversal_score, consensus_accepted, using_ml=False, opp_score=opportunity_score.total_score)

        if label in {"Swing Reversal Watch", "Swing Recovery Watch"}:
            reasons = reversal_reasons + quality_reasons
        else:
            reasons = trend_reasons + quality_reasons

        if not reasons:
            reasons.append("no strong swing pattern detected")

    atr14 = values.get("ATR14", float("nan"))
    latest_close = opportunity_score.latest_close
    
    target_price = latest_close + (3.0 * atr14) if not _missing(atr14) else latest_close
    stop_loss_price = latest_close - (1.0 * atr14) if not _missing(atr14) else latest_close
    dynamic_stop = False
    
    mae_model = _get_mae_model()
    if mae_model is not None and model is not None:
        try:
            predicted_mae = mae_model.predict(df)[0]
            # Safety: Ensure the stop is at least 1.5% away and at most 15% away to avoid extreme predictions
            predicted_mae = max(1.5, min(15.0, predicted_mae))
            # Increase stop padding slightly for volatility
            padded_mae = predicted_mae * 1.1 
            stop_loss_price = latest_close - (latest_close * (padded_mae / 100.0))
            dynamic_stop = True
            reasons.append(f"ML Stop Loss (Dynamic): {padded_mae:.1f}% risk")
        except Exception as e:
            logger.warning(f"Failed to calculate dynamic ML stop: {e}")
            
    position_size = 0.0
    max_risk = 0.0
    if score >= 50 and not _missing(atr14) and latest_close > 0:
        size_suggestion = calculate_position_size(
            win_probability_percent=score,
            entry_price=latest_close,
            stop_loss_price=stop_loss_price,
            target_price=target_price
        )
        position_size = size_suggestion.recommended_weight_percent
        max_risk = size_suggestion.max_risk_percent
        reasons.extend(size_suggestion.reasoning)

    return SwingPrediction(
        score=score,
        label=label,
        reasons=reasons,
        latest_close=latest_close,
        target_price=target_price,
        stop_loss_price=stop_loss_price,
        position_size=position_size,
        max_risk=max_risk,
        dynamic_stop=dynamic_stop
    )


def _trend_continuation_score(values: dict[str, float]) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    trend_strength = values.get("TrendStrength", float("nan"))
    rsi14 = values.get("RSI14", float("nan"))
    macd = values.get("MACD", float("nan"))
    macd_histogram = values.get("MACDHistogram", float("nan"))
    momentum20 = values.get("Momentum20", float("nan"))
    near_high = values.get("NearCloseHigh250Percent", float("nan"))
    rel_volume = values.get("RelVolume20", float("nan"))

    if not _missing(trend_strength):
        score += min(max(trend_strength, 0.0), 100.0) * 0.25
        if trend_strength >= 75:
            reasons.append("trend structure is strong")

    if not _missing(rsi14):
        if 45 <= rsi14 <= 70:
            score += 18.0
            reasons.append("RSI is supportive for swing continuation")
        elif 70 < rsi14 <= 78:
            score += 10.0
            reasons.append("RSI is strong but becoming extended")
        elif rsi14 < 40:
            score -= 8.0
            reasons.append("RSI is weak")

    if not _missing(macd) and macd > 0:
        score += 10.0
        reasons.append("MACD is positive")

    if not _missing(macd_histogram) and macd_histogram > 0:
        score += 10.0
        reasons.append("MACD histogram is positive")

    if not _missing(momentum20):
        if momentum20 >= 10:
            score += 12.0
            reasons.append("20-bar momentum is strong")
        elif momentum20 >= 3:
            score += 8.0
            reasons.append("20-bar momentum is positive")
        elif momentum20 < 0:
            score -= 6.0
            reasons.append("20-bar momentum is negative")

    if not _missing(near_high):
        if near_high >= -5:
            score += 8.0
            reasons.append("price is near its 250-bar closing high")
        elif near_high <= -20:
            score -= 5.0
            reasons.append("price is far below its 250-bar closing high")

    if not _missing(rel_volume):
        if rel_volume >= 1.0:
            score += 7.0
            reasons.append("volume supports the swing setup")
        elif rel_volume < 0.5:
            score -= 5.0
            reasons.append("relative volume is weak")

    return max(0.0, min(score, 100.0)), reasons


def _swing_reversal_score(values: dict[str, float]) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    rsi14 = values.get("RSI14", float("nan"))
    rsi_rebound = values.get("RSIRebound", float("nan"))
    ema20_reclaim = values.get("EMA20Reclaim", float("nan"))
    macd_histogram = values.get("MACDHistogram", float("nan"))
    macd_improvement = values.get("MACDHistogramImprovement", float("nan"))
    volume_spike = values.get("VolumeSpikeFromWeakness", float("nan"))
    momentum5 = values.get("Momentum5", float("nan"))
    momentum20 = values.get("Momentum20", float("nan"))
    near_high = values.get("NearCloseHigh250Percent", float("nan"))

    if not _missing(rsi14):
        if rsi14 <= 35:
            score += 15.0
            reasons.append("RSI is deeply weak/oversold")
        elif rsi14 <= 50:
            score += 10.0
            reasons.append("RSI is in a recovery zone")

    if rsi_rebound == 1.0:
        score += 16.0
        reasons.append("RSI is rebounding")

    if ema20_reclaim == 1.0:
        score += 16.0
        reasons.append("price reclaimed EMA20")

    if not _missing(macd_improvement) and macd_improvement > 0:
        score += 14.0
        reasons.append("MACD histogram is improving")

    if not _missing(macd_histogram) and macd_histogram > 0:
        score += 8.0
        reasons.append("MACD histogram turned positive")

    if volume_spike == 1.0:
        score += 16.0
        reasons.append("volume spiked after weakness")

    if not _missing(momentum5):
        if momentum5 >= 5:
            score += 12.0
            reasons.append("5-bar rebound momentum is strong")
        elif momentum5 > 0:
            score += 7.0
            reasons.append("5-bar rebound momentum is positive")

    if not _missing(momentum20) and momentum20 > 10:
        score += 6.0
        reasons.append("20-bar recovery momentum is strong")

    if not _missing(near_high) and near_high <= -20:
        score += 4.0
        reasons.append("setup has recovery room below prior highs")

    return max(0.0, min(score, 100.0)), reasons


def _quality_adjustment(
    consensus_accepted: bool,
    consensus_confidence: float,
    data_quality_score: float,
) -> tuple[float, list[str]]:
    adjustment = 0.0
    reasons: list[str] = []

    if consensus_accepted:
        adjustment += min(consensus_confidence, 100.0) * 0.05
    else:
        adjustment -= 20.0
        reasons.append("latest close consensus is not accepted")

    if data_quality_score < 60:
        adjustment -= 10.0
        reasons.append("data quality is low")

    return adjustment, reasons


def _label(score: float, trend_score: float, reversal_score: float, consensus_accepted: bool, using_ml: bool = False, opp_score: float = 100.0) -> str:
    if not consensus_accepted:
        return "Low Confidence"

    if opp_score < 40:
        return "Avoid Swing"

    if using_ml:
        if score >= 70 and opp_score >= 60:
            return "Swing Trend Continuation"
        if score >= 60 and opp_score >= 50:
            return "Swing Watchlist"
        return "Avoid Swing"

    if reversal_score >= 70 and reversal_score >= trend_score:
        return "Swing Reversal Watch"

    if trend_score >= 70 and trend_score >= reversal_score:
        return "Swing Trend Continuation"

    if reversal_score >= 60 and reversal_score >= trend_score:
        return "Swing Recovery Watch"

    if score >= 65:
        return "Swing Watchlist"

    return "Avoid Swing"


def _missing(value: float) -> bool:
    return isnan(value)
