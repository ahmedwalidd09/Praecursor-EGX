from dataclasses import dataclass
from math import isnan
from pathlib import Path
import logging

try:
    import pandas as pd
    import xgboost as xgb
    HAS_ML = True
except ImportError:
    HAS_ML = False

from praecursor.scoring.opportunity_score import OpportunityScore

logger = logging.getLogger(__name__)

_NEXT_DAY_MODEL = None
_NEXT_DAY_LGB_MODEL = None
_NEXT_DAY_META = None

def _get_next_day_model():
    global _NEXT_DAY_MODEL
    if not HAS_ML:
        return None
        
    if _NEXT_DAY_MODEL is None:
        try:
            model_path = Path(__file__).resolve().parents[3] / "models" / "xgboost_next_day.json"
            if model_path.exists():
                _NEXT_DAY_MODEL = xgb.XGBClassifier()
                _NEXT_DAY_MODEL.load_model(str(model_path))
            else:
                _NEXT_DAY_MODEL = False
        except Exception as e:
            logger.error(f"Failed to load next day ML model: {e}")
            _NEXT_DAY_MODEL = False
            
    return _NEXT_DAY_MODEL if _NEXT_DAY_MODEL is not False else None

def _get_next_day_lgb_model():
    global _NEXT_DAY_LGB_MODEL
    if _NEXT_DAY_LGB_MODEL is None:
        try:
            import lightgbm as lgb
            model_path = Path(__file__).resolve().parents[3] / "models" / "lightgbm_next_day.txt"
            if model_path.exists():
                _NEXT_DAY_LGB_MODEL = lgb.Booster(model_file=str(model_path))
            else:
                _NEXT_DAY_LGB_MODEL = False
        except Exception:
            _NEXT_DAY_LGB_MODEL = False
    return _NEXT_DAY_LGB_MODEL if _NEXT_DAY_LGB_MODEL is not False else None

def _get_next_day_meta():
    global _NEXT_DAY_META
    if _NEXT_DAY_META is None:
        try:
            import json
            meta_path = Path(__file__).resolve().parents[3] / "models" / "xgboost_next_day_meta.json"
            if meta_path.exists():
                with open(meta_path, "r") as f:
                    _NEXT_DAY_META = json.load(f)
            else:
                _NEXT_DAY_META = {"threshold": 0.5}
        except Exception as e:
            logger.error(f"Failed to load next day model metadata: {e}")
            _NEXT_DAY_META = {"threshold": 0.5}
    return _NEXT_DAY_META


@dataclass(frozen=True)
class NextDayPrediction:
    """Next-session breakout/follow-through assessment."""

    score: float
    label: str
    reasons: list[str]
    latest_close: float = 0.0
    target_price: float = 0.0
    stop_loss_price: float = 0.0

    @property
    def reasons_text(self) -> str:
        return "; ".join(self.reasons)


def calculate_next_day_prediction(
    opportunity_score: OpportunityScore,
    consensus_accepted: bool = True,
    consensus_confidence: float = 40.0,
    data_quality_score: float = 100.0,
) -> NextDayPrediction:
    """Calculate next-session breakout/follow-through prediction."""
    values = opportunity_score.indicator_values
    score = 0.0
    reasons: list[str] = []

    trend_strength = values.get("TrendStrength", float("nan"))
    breakout20 = values.get("Breakout20", float("nan"))
    breakout50 = values.get("Breakout50", float("nan"))
    volume_confirmed_breakout = values.get("VolumeConfirmedBreakout", float("nan"))
    near_high = values.get("NearCloseHigh250Percent", float("nan"))
    macd = values.get("MACD", float("nan"))
    macd_histogram = values.get("MACDHistogram", float("nan"))
    momentum20 = values.get("Momentum20", float("nan"))
    relative_volume20 = values.get("RelVolume20", float("nan"))
    rsi14 = values.get("RSI14", float("nan"))

    model = _get_next_day_model()
    
    if model is not None:
        features = [
            "RSI14", "RelVolume20", "MACDHistogram", "Momentum20", 
            "Breakout20", "Breakout50", "RSIRebound", "EMA20Reclaim", 
            "MACDHistogramImprovement", "VolumeSpikeFromWeakness", "Momentum5", "BBW20",
            "MTF_Trend", "VPOC_Distance", "ADX14", "ROC10", "StochRSI", "VWAPMom10",
            "AvgTurnover20", "ClosedAtLimitUp", "ATRPercent14",  # v0.4.0: native volatility feature
            "Momentum1", "RSISlope3", "ConsecutiveGreen", "DayOfWeek",  # v0.5.0: temporal features
        ]
        csv_features = [
            "rsi14", "rel_volume20", "macd_histogram", "momentum20", "breakout20", "breakout50",
            "rsi_rebound", "ema20_reclaim", "macd_histogram_improvement", "volume_spike_from_weakness", "momentum5", "bbw20",
            "mtf_trend", "vpoc_distance", "adx14", "roc10", "stoch_rsi", "vwap_mom10",
            "avg_turnover_20", "closed_at_limit_up", "atr_pct14",  # v0.4.0
            "momentum1", "rsi_slope3", "consecutive_green", "day_of_week",  # v0.5.0
        ]
        
        row_data = {csv_name: values.get(orig_name, 0.0) for csv_name, orig_name in zip(csv_features, features)}
        # Replace NaN with 0 for ML
        for k, v in row_data.items():
            if v != v:  # NaN check
                row_data[k] = 0.0
        df = pd.DataFrame([row_data])
        
        try:
            # Try 25 features (v0.5.0 model) first, then fall back to 21, 20, 14
            try:
                prob = model.predict_proba(df.values)[0][1]
            except Exception:
                old_features_21 = [
                    "rsi14", "rel_volume20", "macd_histogram", "momentum20", "breakout20", "breakout50",
                    "rsi_rebound", "ema20_reclaim", "macd_histogram_improvement", "volume_spike_from_weakness", "momentum5", "bbw20",
                    "mtf_trend", "vpoc_distance", "adx14", "roc10", "stoch_rsi", "vwap_mom10",
                    "avg_turnover_20", "closed_at_limit_up", "atr_pct14"
                ]
                try:
                    prob = model.predict_proba(df[old_features_21].values)[0][1]
                except Exception:
                    old_features_20 = [
                        "rsi14", "rel_volume20", "macd_histogram", "momentum20", "breakout20", "breakout50",
                        "rsi_rebound", "ema20_reclaim", "macd_histogram_improvement", "volume_spike_from_weakness", "momentum5", "bbw20",
                        "mtf_trend", "vpoc_distance", "adx14", "roc10", "stoch_rsi", "vwap_mom10",
                        "avg_turnover_20", "closed_at_limit_up"
                    ]
                    try:
                        prob = model.predict_proba(df[old_features_20].values)[0][1]
                    except Exception:
                        old_features_14 = [
                            "rsi14", "rel_volume20", "macd_histogram", "momentum20", "breakout20", "breakout50",
                            "rsi_rebound", "ema20_reclaim", "macd_histogram_improvement", "volume_spike_from_weakness", "momentum5", "bbw20",
                            "mtf_trend", "vpoc_distance"
                        ]
                        prob = model.predict_proba(df[old_features_14].values)[0][1]
        except Exception:
            prob = 0.0
        
        # Ensemble with LightGBM if available
        lgb_model = _get_next_day_lgb_model()
        if lgb_model is not None:
            try:
                lgb_prob = lgb_model.predict(df.values)[0]
                prob = 0.6 * prob + 0.4 * lgb_prob
                reasons.append(f"Ensemble (XGB+LGB)")
            except Exception:
                pass
        
        score = prob * 100.0
        
        # Apply EGX30 Market Regime logic
        from praecursor.scoring.regime import MarketRegimeModel
        regime_info = MarketRegimeModel().get_latest_regime()
        regime = regime_info.get("regime", "Unknown")
        if "Bear" in regime:
            score *= 0.90  # Light penalty for breakouts in a bear market
            reasons.append(f"Regime {regime}: Penalizing breakout score")
        elif "Bull" in regime:
            score *= 1.15
            reasons.append(f"Regime {regime}: Boosting breakout score")
            
        reasons.append(f"AI Probability: {score:.1f}%")
        meta = _get_next_day_meta()
        threshold = meta.get("threshold", 0.5) if meta else 0.5
        if score >= threshold * 100:
            reasons.append("ML model predicts a positive 1-day return")
            
        if not consensus_accepted:
            score -= 20.0
            reasons.append("latest close consensus is not accepted")

        if data_quality_score < 60:
            score -= 10.0
            reasons.append("data quality is low")
            
    else:
        if not _missing(trend_strength):
            score += min(max(trend_strength, 0.0), 100.0) * 0.18
            if trend_strength >= 75:
                reasons.append("trend structure is strong")

        if breakout20 == 1.0:
            score += 18.0
            reasons.append("20-bar closing breakout is active")
        if breakout50 == 1.0:
            score += 12.0
            reasons.append("50-bar closing breakout is active")
        if volume_confirmed_breakout == 1.0:
            score += 18.0
            reasons.append("breakout is volume-confirmed")

        if not _missing(near_high):
            if near_high >= -3.0:
                score += 6.0
                reasons.append("close is within 3% of 250-bar closing high")
            elif near_high >= -7.0:
                score += 3.0
                reasons.append("close is near its 250-bar closing high")

        if not _missing(macd) and macd > 0:
            score += 5.0
        if not _missing(macd_histogram) and macd_histogram > 0:
            score += 8.0
            reasons.append("MACD acceleration is positive")

        if not _missing(momentum20):
            if momentum20 >= 10.0:
                score += 9.0
                reasons.append("20-bar momentum is strong")
            elif momentum20 >= 3.0:
                score += 5.0
                reasons.append("20-bar momentum is positive")
            elif momentum20 < 0:
                score -= 5.0
                reasons.append("20-bar momentum is negative")

        momentum5 = values.get("Momentum5", float("nan"))
        if not _missing(momentum5) and momentum5 >= 5.0:
            score += 8.0
            reasons.append("5-bar momentum is strong")

        volume_spike = values.get("VolumeSpikeFromWeakness", float("nan"))
        if volume_spike == 1.0:
            score += 15.0
            reasons.append("volume spiked after weakness")

        rsi_rebound = values.get("RSIRebound", float("nan"))
        if rsi_rebound == 1.0:
            score += 12.0
            reasons.append("RSI is rebounding")

        ema20_reclaim = values.get("EMA20Reclaim", float("nan"))
        if ema20_reclaim == 1.0:
            score += 10.0
            reasons.append("price reclaimed EMA20")

        if not _missing(relative_volume20):
            if relative_volume20 >= 1.5:
                score += 20.0
                reasons.append("relative volume is strongly elevated")
            elif relative_volume20 >= 1.0:
                score += 12.0
                reasons.append("relative volume supports the move")
            elif relative_volume20 >= 0.75:
                score += 5.0
                reasons.append("relative volume is acceptable but not strong")
            else:
                reasons.append("relative volume is weak")

        if consensus_accepted:
            score += min(consensus_confidence, 100.0) * 0.05
        else:
            score -= 20.0
            reasons.append("latest close consensus is not accepted")

        if data_quality_score < 60:
            score -= 10.0
            reasons.append("data quality is low")

        if not _missing(rsi14):
            if rsi14 > 80:
                score -= 18.0
                reasons.append("RSI is extremely overextended")
            elif rsi14 > 75:
                score -= 10.0
                reasons.append("RSI is overextended")
            elif rsi14 < 45:
                score -= 8.0
                reasons.append("RSI is not supportive")

    score = max(0.0, min(score, 100.0))
    
    # ----------------------------------------------------
    # Smart Volatility & Liquidity Overrides
    # ----------------------------------------------------
    atr_pct = values.get("ATRPercent14", float("nan"))
    turnover20 = values.get("AvgTurnover20", float("nan"))
    
    if not _missing(atr_pct):
        # 1. Low Volatility Penalty (Mega-caps or stagnant stocks)
        if atr_pct < 2.5:
            score -= 20.0
            reasons.append(f"Low volatility (ATR {atr_pct:.1f}% < 2.5%): Deprioritized for rapid next-day moves")
        
        # 2. Explosive Small/Mid-Cap Bonus
        elif atr_pct > 5.0 and not _missing(turnover20) and turnover20 > 2_000_000:
            score += 12.0
            reasons.append(f"High volatility (ATR {atr_pct:.1f}% > 5.0%) with acceptable liquidity: Explosive setup")
            
        # 3. Heavy Mega-Cap Penalty
        if not _missing(turnover20) and turnover20 > 100_000_000 and atr_pct < 4.0:
            score -= 15.0
            reasons.append(f"Heavy mega-cap (Turnover > 100M) lacks volatility for fast intraday swings")

    score = max(0.0, min(score, 100.0))
    label = _label(score, rsi14, breakout20, breakout50, volume_confirmed_breakout, consensus_accepted, opp_score=opportunity_score.score_percent)

    if not reasons:
        reasons.append("no strong next-day breakout/follow-through pattern detected")

    atr14 = values.get("ATR14", float("nan"))
    latest_close = opportunity_score.latest_close
    
    # --- Adaptive Target Pricing (v0.4.0) ---
    # Multipliers scale with volatility tier so explosive stocks get wider targets
    # and low-vol stocks get realistic, tighter targets. Regime further adjusts.
    atr_pct_for_target = values.get("ATRPercent14", float("nan"))
    if not _missing(atr_pct_for_target) and atr_pct_for_target >= 5.0:
        target_mult, stop_mult = 3.0, 1.5   # Explosive stocks
    elif not _missing(atr_pct_for_target) and atr_pct_for_target >= 3.0:
        target_mult, stop_mult = 2.5, 1.2   # Normal volatility
    else:
        target_mult, stop_mult = 2.0, 1.0   # Low-vol: tighter, more realistic

    # Regime adjustment (uses cached _REGIME_CACHE — no duplicate API call)
    from praecursor.scoring.regime import MarketRegimeModel
    _regime_for_target = MarketRegimeModel().get_latest_regime()
    _regime_name = _regime_for_target.get("regime", "Unknown")
    if "Bear" in _regime_name:
        target_mult *= 0.8
    elif "Bull" in _regime_name:
        target_mult *= 1.1

    target_price = latest_close + (target_mult * atr14) if not _missing(atr14) else latest_close
    stop_loss_price = latest_close - (stop_mult * atr14) if not _missing(atr14) else latest_close

    return NextDayPrediction(
        score=score, 
        label=label, 
        reasons=reasons,
        latest_close=latest_close,
        target_price=target_price,
        stop_loss_price=stop_loss_price,
    )


def _label(
    score: float,
    rsi14: float,
    breakout20: float,
    breakout50: float,
    volume_confirmed_breakout: float,
    consensus_accepted: bool,
    opp_score: float = 100.0,
) -> str:
    if not consensus_accepted:
        return "Low Confidence"

    if opp_score < 40:
        return "Avoid Tomorrow"

    is_breakout = breakout20 == 1.0 and breakout50 == 1.0
    is_volume_confirmed = volume_confirmed_breakout == 1.0
    is_overextended = not _missing(rsi14) and rsi14 > 75

    if score >= 75 and is_breakout and is_volume_confirmed:
        if is_overextended:
            return "Next-Day Breakout Candidate - Extended"
        return "Next-Day Breakout Candidate"

    if score >= 52 and opp_score >= 60:
        return "High-Priority Next-Day Watch"

    if score >= 48 and opp_score >= 50:
        return "Next-Day Candidate"

    if score >= 45 and opp_score >= 40:
        return "Watchlist Tomorrow"

    return "Avoid Tomorrow"

def _missing(value: float) -> bool:
    return isnan(value)
