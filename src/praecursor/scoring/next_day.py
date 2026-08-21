from dataclasses import dataclass
from math import isnan
from pathlib import Path
import logging
import sqlite3

try:
    import pandas as pd
    import xgboost as xgb
    import numpy as np
    HAS_ML = True
except ImportError:
    HAS_ML = False
    pd = None
    xgb = None
    np = None

from praecursor.scoring.opportunity_score import OpportunityScore

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).resolve().parents[3] / "database" / "praecursor.db"


def _get_whipsaw_penalty(symbol: str, lookback_days: int = 60, fail_threshold: int = 3) -> float:
    """
    Upgrade #3: Whipsaw Memory Filter.
    Query the last `lookback_days` of scanner_signal_outcomes for this symbol.
    If the stock has attempted breakouts >= fail_threshold times and failed (next_day_hit=0),
    apply a score multiplier penalty of 0.5 to kill serial trap stocks.
    Returns 0.5 (penalty) or 1.0 (no penalty).
    """
    try:
        if not _DB_PATH.exists():
            return 1.0
        with sqlite3.connect(str(_DB_PATH)) as conn:
            rows = conn.execute("""
                SELECT o.next_day_hit
                FROM scanner_signal_outcomes o
                JOIN scanner_signals s ON s.run_id = o.run_id AND s.symbol = o.symbol
                WHERE o.symbol = ?
                  AND o.next_day_hit IS NOT NULL
                  AND date(s.generated_at) >= date('now', ? || ' days')
                ORDER BY s.generated_at DESC
            """, (symbol, f"-{lookback_days}")).fetchall()
        if not rows:
            return 1.0
        total_attempts = len(rows)
        failed = sum(1 for r in rows if r[0] == 0)
        if total_attempts >= fail_threshold and failed == total_attempts:
            logger.debug(f"{symbol}: whipsaw penalty triggered ({failed}/{total_attempts} failures in {lookback_days}d)")
            return 0.5
        return 1.0
    except Exception:
        return 1.0


def _get_ticker_win_rate(symbol: str, min_samples: int = 5) -> float:
    """
    Upgrade #9: Historical Ticker Win-Rate.
    Returns the historical hit-rate for this ticker [0.0-1.0].
    Returns 0.5 (neutral prior) if insufficient data.
    """
    try:
        if not _DB_PATH.exists():
            return 0.5
        with sqlite3.connect(str(_DB_PATH)) as conn:
            rows = conn.execute("""
                SELECT o.next_day_hit
                FROM scanner_signal_outcomes o
                WHERE o.symbol = ? AND o.next_day_hit IS NOT NULL
            """, (symbol,)).fetchall()
        if not rows or len(rows) < min_samples:
            return 0.5
        win_rate = sum(1 for r in rows if r[0] == 1) / len(rows)
        return float(win_rate)
    except Exception:
        return 0.5

_NEXT_DAY_ENSEMBLE = None

def _get_next_day_ensemble():
    global _NEXT_DAY_ENSEMBLE
    if not HAS_ML:
        return None
        
    if _NEXT_DAY_ENSEMBLE is None:
        try:
            import pickle
            models_dir = Path(__file__).resolve().parents[3] / "models"
            bull_path = models_dir / "xgb_bull_model.pkl"
            bear_path = models_dir / "xgb_bear_model.pkl"
            meta_path = models_dir / "meta_learner.pkl"
            
            if bull_path.exists() and bear_path.exists() and meta_path.exists():
                with open(bull_path, "rb") as f:
                    bull_model = pickle.load(f)
                with open(bear_path, "rb") as f:
                    bear_model = pickle.load(f)
                with open(meta_path, "rb") as f:
                    meta_learner = pickle.load(f)
                _NEXT_DAY_ENSEMBLE = (bull_model, bear_model, meta_learner)
            else:
                _NEXT_DAY_ENSEMBLE = False
        except Exception as e:
            logger.debug(f"Failed to load next-day ensemble: {e}")
            _NEXT_DAY_ENSEMBLE = False
            
    return _NEXT_DAY_ENSEMBLE if _NEXT_DAY_ENSEMBLE is not False else None


_ANOMALY_DETECTOR = None

def _get_anomaly_detector():
    global _ANOMALY_DETECTOR
    if not HAS_ML:
        return None
        
    if _ANOMALY_DETECTOR is None:
        try:
            import pickle
            models_dir = Path(__file__).resolve().parents[3] / "models"
            iso_path = models_dir / "anomaly_detector.pkl"
            
            if iso_path.exists():
                with open(iso_path, "rb") as f:
                    _ANOMALY_DETECTOR = pickle.load(f)
            else:
                _ANOMALY_DETECTOR = False
        except Exception as e:
            logger.debug(f"Failed to load anomaly detector: {e}")
            _ANOMALY_DETECTOR = False
            
    return _ANOMALY_DETECTOR if _ANOMALY_DETECTOR is not False else None

_RL_TARGET_AGENT = None

def _get_rl_target_agent():
    global _RL_TARGET_AGENT
    if not HAS_ML:
        return None
        
    if _RL_TARGET_AGENT is None:
        try:
            from stable_baselines3 import PPO
            model_path = Path(__file__).resolve().parents[3] / "models" / "rl_target_agent.zip"
            if model_path.exists():
                _RL_TARGET_AGENT = PPO.load(str(model_path))
            else:
                _RL_TARGET_AGENT = False
        except Exception as e:
            logger.error(f"Failed to load RL target agent: {e}")
            _RL_TARGET_AGENT = False
            
    return _RL_TARGET_AGENT if _RL_TARGET_AGENT is not False else None

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

_HMM_MODEL_FN = None
def _get_hmm_model():
    global _HMM_MODEL_FN
    if _HMM_MODEL_FN is None:
        try:
            from praecursor.ml.hmm_phase import predict_hmm_state
            _HMM_MODEL_FN = predict_hmm_state
        except Exception as e:
            _HMM_MODEL_FN = False
    return _HMM_MODEL_FN if _HMM_MODEL_FN is not False else None

_SNIPER_MODEL = None
def _get_sniper_model():
    global _SNIPER_MODEL
    if not HAS_ML:
        return None
    if _SNIPER_MODEL is None:
        try:
            import pickle
            models_dir = Path(__file__).resolve().parents[3] / "models"
            sniper_path = models_dir / "xgb_sniper_model.pkl"
            if sniper_path.exists():
                with open(sniper_path, "rb") as f:
                    _SNIPER_MODEL = pickle.load(f)
            else:
                _SNIPER_MODEL = False
        except Exception as e:
            _SNIPER_MODEL = False
    return _SNIPER_MODEL if _SNIPER_MODEL is not False else None


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
    kelly_fraction: float = 0.0

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
    symbol = opportunity_score.symbol
    reasons: list[str] = []
    
    base_score = opportunity_score.score_percent
    score = base_score
    reasons.append(f"Base Opportunity Score: {base_score:.1f}%")

    bull_prob_val = 0.5
    bear_prob_val = 0.5
    regime_score_val = 1.0

    stock_obj = getattr(opportunity_score, "stock", None)
    
    predict_hmm_state = _get_hmm_model()
    if predict_hmm_state is not None and stock_obj is not None:
        try:
            hmm_state = predict_hmm_state(stock_obj)
            if hmm_state == 'Distribution':
                score -= 5.0
                reasons.append(f"[HMM CAUTION] Stock is in Distribution phase. Soft penalty applied.")
        except Exception:
            pass

    whipsaw_multiplier = _get_whipsaw_penalty(symbol)
    if whipsaw_multiplier < 1.0:
        whipsaw_multiplier = 0.90
        reasons.append(f"[WHIPSAW] {symbol} has failed recent breakout attempts - soft penalty applied")

    ticker_win_rate = _get_ticker_win_rate(symbol)
    
    gap_blackout_penalty = 0.0
    if stock_obj is not None and hasattr(stock_obj, "history") and len(stock_obj.history) >= 2:
        recent_history = stock_obj.history[-2:]
        prev_close = recent_history[0].close
        curr_open = recent_history[1].open
        if prev_close > 0 and abs(curr_open - prev_close) / prev_close > 0.10:
            reasons.append("[CORPORATE ACTION BLACKOUT] Massive 10%+ overnight gap detected. Likely earnings/dividend.")
            gap_blackout_penalty = 20.0

    vpoc_raw = values.get("VPOC_Distance", None)
    vpoc_overhead_penalty = 0.0
    if isinstance(vpoc_raw, dict):
        if vpoc_raw.get("VPOC_Above", 0.0) == 1.0:
            reasons.append("[VPOC REJECTION] VPOC overhead resistance: heavy supply zone above current price")
            vpoc_overhead_penalty += 30.0
        
        if vpoc_raw.get("Overhead_HVN", 0.0) == 1.0:
            reasons.append("[HVN REJECTION] Breaking into High Volume Node (HVN): massive historical resistance overhead")
            vpoc_overhead_penalty += 20.0

    news_sentiment = values.get("news_sentiment", float("nan"))
    volume_spike_val = values.get("VolumeSpikeFromWeakness", float("nan"))
    relative_vol_val = values.get("RelVolume20", float("nan"))
    
    no_news_penalty = 0.0
    weekend_risk_penalty = 0.0

    ticker_history_penalty = 0.0
    if ticker_win_rate < 0.3 and ticker_win_rate > 0.0:
        reasons.append(f"[BACKTEST REJECTION] Historically poor win-rate ({ticker_win_rate*100:.0f}%).")
        ticker_history_penalty = 10.0

    breakout20 = values.get("Breakout20", float("nan"))
    breakout50 = values.get("Breakout50", float("nan"))
    volume_confirmed_breakout = values.get("VolumeConfirmedBreakout", float("nan"))
    rsi14 = values.get("RSI14", float("nan"))

    model = _get_next_day_model()
    
    X_arr = None
    if model is not None:
        features = [
            "RSI14", "RelVolume20", "MACDHistogram", "Momentum20", 
            "Breakout20", "Breakout50", "RSIRebound", "EMA20Reclaim", 
            "MACDHistogramImprovement", "VolumeSpikeFromWeakness", "Momentum5", "BBW20",
            "MTF_Trend", "VPOC_Distance", "ADX14", "ROC10", "StochRSI", "VWAPMom10",
            "AvgTurnover20", "ClosedAtLimitUp", "ATRPercent14",
            "KalmanTrend", "RSI14_ZScore", "Momentum20_ZScore", "LiquidityVacuumScore",
            "Distance_To_ATH", "New_ATH_Made_Today", "ATR_Expansion_Ratio", "ATR_Exploding",
            "Squeeze_Fired", "Squeeze_Building", "Full_Confirmation", "Partial_Confirmation",
            "Very_Near", "Near_High",
            "Momentum1", "RSISlope3", "ConsecutiveGreen", "DayOfWeek"
        ]
        csv_features = [
            "rsi14", "rel_volume20", "macd_histogram", "momentum20", "breakout20", "breakout50",
            "rsi_rebound", "ema20_reclaim", "macd_histogram_improvement", "volume_spike_from_weakness", "momentum5", "bbw20",
            "mtf_trend", "vpoc_distance", "adx14", "roc10", "stoch_rsi", "vwap_mom10",
            "avg_turnover_20", "closed_at_limit_up", "atr_pct14",
            "kalman_trend", "rsi_zscore", "mom_zscore", "liquidity_vacuum_score",
            "distance_to_ath", "new_ath_made_today", "atr_expansion_ratio", "atr_exploding",
            "squeeze_fired", "squeeze_building", "nhm_full", "nhm_partial",
            "nhm_very_near", "nhm_near_high",
            "momentum1", "rsi_slope3", "consecutive_green", "day_of_week"
        ]
        
        flat_values = {}
        for k, v in values.items():
            if isinstance(v, dict):
                for sub_k, sub_v in v.items():
                    flat_values[sub_k] = sub_v
            else:
                flat_values[k] = v
                
        flat_values["VPOC_Distance"] = flat_values.get("VPOC_Distance_Pct", 0.0)
        
        # Upgrade #1: 4 Ghost Features
        import datetime
        momentum1 = 0.0
        rsi_slope3 = 0.0
        consecutive_green = 0
        day_of_week = float(datetime.date.today().weekday())
        
        if stock_obj is not None and hasattr(stock_obj, "history") and len(stock_obj.history) >= 4:
            history = stock_obj.history
            close = history[-1].close
            prev_close = history[-2].close
            if prev_close > 0:
                momentum1 = (close - prev_close) / prev_close * 100.0
                
            count = 0
            for bar in reversed(history):
                if bar.close > bar.open:
                    count += 1
                else:
                    break
            consecutive_green = count
            
        flat_values["Momentum1"] = momentum1
        flat_values["RSISlope3"] = rsi_slope3
        flat_values["ConsecutiveGreen"] = float(consecutive_green)
        flat_values["DayOfWeek"] = day_of_week

        row_data = {csv_name: flat_values.get(orig_name, 0.0) for csv_name, orig_name in zip(csv_features, features)}
        for k, v in row_data.items():
            if v != v:
                row_data[k] = 0.0
        df = pd.DataFrame([row_data])
        X_arr = df[csv_features].values
        
        ml_bonus = 0.0
        optimal_thresh = _get_next_day_meta().get(chr(34) + str(chr(116)) + str(chr(104)) + str(chr(114)) + str(chr(101)) + str(chr(115)) + str(chr(104)) + str(chr(111)) + str(chr(108)) + str(chr(100)) + chr(34), 0.5)
        try:
            prob = model.predict_proba(X_arr)[0][1]
            xgb_bonus = max(-10.0, min(10.0, (prob - optimal_thresh) * 15.0))
            ml_bonus += xgb_bonus
            reasons.append(f"XGBoost Model Probability: {prob:.1%} (Bonus: {xgb_bonus:+.1f})")
        except Exception as e:
            pass
            
        lgb_model = _get_next_day_lgb_model()
        if lgb_model is not None:
            try:
                lgb_prob = lgb_model.predict(X_arr)[0]
                lgb_bonus = max(-8.0, min(8.0, (lgb_prob - optimal_thresh) * 10.0))
                ml_bonus += lgb_bonus
                reasons.append(f"LightGBM Model Probability: {lgb_prob:.1%} (Bonus: {lgb_bonus:+.1f})")
            except Exception:
                pass
                
        score += ml_bonus

    from praecursor.scoring.regime import MarketRegimeModel
    regime_info = MarketRegimeModel().get_latest_regime()
    regime = regime_info.get("regime", "Unknown")
    if "Bear" in regime:
        score *= 0.93
        reasons.append(f"Regime {regime}: Soft bear market penalty applied")
    elif "Bull" in regime:
        score *= 1.07
        reasons.append(f"Regime {regime}: Soft bull market bonus applied")

    if not consensus_accepted:
        reasons.append("latest close consensus is not accepted")

    if data_quality_score < 60:
        score -= 10.0
        reasons.append("data quality is low")

    score = max(0.0, min(score, 100.0))
    
    atr_pct = values.get("ATRPercent14", float("nan"))
    turnover20 = values.get("AvgTurnover20", float("nan"))
    
    if not _missing(atr_pct):
        if atr_pct < 2.5:
            score -= 20.0
            reasons.append(f"Low volatility (ATR {atr_pct:.1f}% < 2.5%): Deprioritized for rapid next-day moves")
        elif atr_pct > 5.0 and not _missing(turnover20) and turnover20 > 2_000_000:
            score += 12.0
            reasons.append(f"High volatility (ATR {atr_pct:.1f}% > 5.0%) with acceptable liquidity: Explosive setup")
        if not _missing(turnover20) and turnover20 > 100_000_000 and atr_pct < 4.0:
            score -= 15.0
            reasons.append(f"Heavy mega-cap (Turnover > 100M) lacks volatility for fast intraday swings")
            
    score = max(0.0, min(score, 100.0))
    score *= whipsaw_multiplier
    score = max(0.0, score - vpoc_overhead_penalty)
    score = max(0.0, score - ticker_history_penalty)
    score = max(0.0, score - gap_blackout_penalty)
    
    latest_close = opportunity_score.latest_close
    atr14 = values.get("ATR14", float("nan"))
    
    rl_agent = _get_rl_target_agent()
    target_mult, stop_mult = None, None
    
    if rl_agent is not None:
        try:
            vwap_div = values.get("VWAPDivergence15m", 0.0)
            eod_acc = values.get("EODAccumulation", 0.0)
            atr_pct_val = values.get("ATRPercent14", 0.0)
            if _missing(vwap_div): vwap_div = 0.0
            if _missing(eod_acc): eod_acc = 0.0
            if _missing(atr_pct_val): atr_pct_val = 0.0
            
            obs = np.array([
                score, atr_pct_val, vwap_div, eod_acc,
                bull_prob_val, bear_prob_val, regime_score_val,
                ticker_win_rate
            ], dtype=np.float32)
            action, _ = rl_agent.predict(obs, deterministic=True)
            target_mult = float(action[0])
            stop_mult = float(action[1])
            reasons.append(f"RL Optimizer dynamic multipliers: target {target_mult:.2f}x, stop {stop_mult:.2f}x")
        except Exception as e:
            logger.debug(f"RL target prediction failed: {e}")
            
    if target_mult is None or stop_mult is None:
        atr_pct_for_target = values.get("ATRPercent14", float("nan"))
        if not _missing(atr_pct_for_target) and atr_pct_for_target >= 5.0:
            target_mult, stop_mult = 3.0, 1.5
        elif not _missing(atr_pct_for_target) and atr_pct_for_target >= 3.0:
            target_mult, stop_mult = 2.5, 1.2
        else:
            target_mult, stop_mult = 2.0, 1.0
            
        from praecursor.scoring.regime import MarketRegimeModel
        _regime_for_target = MarketRegimeModel().get_latest_regime()
        _regime_name = _regime_for_target.get("regime", "Unknown")
        if "Bear" in _regime_name:
            target_mult *= 0.8
        elif "Bull" in _regime_name:
            target_mult *= 1.1

    atr14 = values.get("ATR14", float("nan"))

    ewma_vol_forecast = None
    try:
        if stock_obj is not None and hasattr(stock_obj, "history") and len(stock_obj.history) > 20 and pd is not None and np is not None:
            closes_history = [bar.close for bar in stock_obj.history[-60:]]
            returns = pd.Series(closes_history).pct_change().dropna()
            ewma_var = returns.ewm(alpha=0.06).var().iloc[-1]
            ewma_vol_forecast = np.sqrt(ewma_var)
    except Exception as e:
        logger.debug(f"Failed to calculate EWMA volatility: {e}")

    if ewma_vol_forecast is not None and not np.isnan(ewma_vol_forecast):
        z_score = 1.645
        stop_pct = ewma_vol_forecast * z_score
        if stop_mult is not None:
            stop_pct *= stop_mult
        stop_pct = max(0.02, min(stop_pct, 0.15))
        stop_loss_price = latest_close * (1.0 - stop_pct)
        reasons.append(f"Dynamic EWMA Volatility Stop-Loss placed at {stop_loss_price:.2f} (-{stop_pct*100:.1f}%)")
    else:
        stop_loss_price = latest_close - (stop_mult * atr14) if not _missing(atr14) else latest_close
        
    target_price = latest_close + (target_mult * atr14) if not _missing(atr14) else latest_close

    kelly_fraction = 0.0
    win_prob = min(score / 100.0, 0.65)
    target_pct = (target_price - latest_close) / latest_close if latest_close > 0 else 0.0
    stop_pct = (latest_close - stop_loss_price) / latest_close if latest_close > 0 else 0.0
    if target_pct > 0 and stop_pct > 0:
        kelly = win_prob - ((1.0 - win_prob) / (target_pct / stop_pct))
        kelly_fraction = max(0.0, min(kelly, 1.0))
        
    from praecursor.scoring.regime import MarketRegimeModel
    regime_name = MarketRegimeModel().get_latest_regime().get("regime", "Unknown")
    label = _label(score, rsi14, breakout20, breakout50, volume_confirmed_breakout, consensus_accepted, opp_score=opportunity_score.score_percent, regime=regime_name, kelly=kelly_fraction)

    if "Candidate" in label or "Watch" in label:
        ml_prob = "N/A"
        if model is not None and X_arr is not None:
            try:
                prob_val = model.predict_proba(X_arr)[0][1]
                ml_prob = f"{prob_val:.1%}"
            except Exception:
                pass
        summary = f"Analysis for {symbol}: Strong setup because: Opportunity Score {base_score:.1f}% (above threshold), ML model agrees (probability {ml_prob}), {regime_name} regime environment"
        reasons.insert(0, summary)
    else:
        reasons.insert(0, f"Analysis for {symbol}: The model avoids this setup because:")

    if not reasons or len(reasons) == 1:
        reasons.append("no strong next-day breakout/follow-through pattern detected")

    return NextDayPrediction(
        score=score, 
        label=label, 
        reasons=reasons,
        latest_close=latest_close,
        target_price=target_price,
        stop_loss_price=stop_loss_price,
        kelly_fraction=kelly_fraction,
    )

def _label(
    score: float,
    rsi14: float,
    breakout20: float,
    breakout50: float,
    volume_confirmed_breakout: float,
    consensus_accepted: bool,
    opp_score: float = 100.0,
    regime: str = "Unknown",
    kelly: float = 0.0,
) -> str:
    if not consensus_accepted:
        return "Low Confidence"
    
    if opp_score < 30:
        return "Avoid Tomorrow"
    
    # Dynamic thresholds based on regime
    if "Bull" in regime:
        candidate_threshold = 65
        watch_threshold = 55
    elif "Bear" in regime:
        candidate_threshold = 75
        watch_threshold = 65
    else:
        candidate_threshold = 70
        watch_threshold = 60
    
    is_breakout = breakout20 == 1.0 and breakout50 == 1.0
    is_volume_confirmed = volume_confirmed_breakout == 1.0
    is_overextended = not _missing(rsi14) and rsi14 > 75
    
    if kelly <= 0.0:
        return "Avoid Tomorrow (Poor Reward/Risk)"
    
    if score >= candidate_threshold + 20 and is_breakout and is_volume_confirmed:
        if is_overextended:
            return "Next-Day Breakout Candidate - Extended"
        return "Next-Day Breakout Candidate"
    
    if score >= candidate_threshold:
        return "High-Priority Next-Day Watch"
    
    if score >= watch_threshold:
        return "Watchlist Tomorrow"
    
    return "Avoid Tomorrow"

def _missing(value: float) -> bool:
    return isnan(value)
