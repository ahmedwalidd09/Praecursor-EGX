from dataclasses import dataclass
from math import isnan
from pathlib import Path
from typing import Any
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

# EGX Circuit Breaker Limits (most stocks are 20%, some are restricted)
_CIRCUIT_BREAKER_LIMITS = {
    # Default is 0.20 (20%) for most EGX stocks
    # Add restricted tickers here as they're identified
}
_DEFAULT_CIRCUIT_BREAKER = 0.20


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
    Historical Ticker Win-Rate.
    Returns the hit rate float [0.0-1.0].
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
        if not rows:
            return 0.5
        win_rate = sum(1 for r in rows if r[0] == 1) / len(rows)
        return float(win_rate)
    except Exception:
        return 0.5


def _get_ticker_historical_win_rate(symbol: str, min_samples: int = 5) -> tuple[float, int]:
    """
    Historical Ticker Win-Rate with Sample Count.
    Returns (win_rate, total_samples).
    """
    try:
        if not _DB_PATH.exists():
            return 0.5, 0
        with sqlite3.connect(str(_DB_PATH)) as conn:
            rows = conn.execute("""
                SELECT o.next_day_hit
                FROM scanner_signal_outcomes o
                WHERE o.symbol = ? AND o.next_day_hit IS NOT NULL
            """, (symbol,)).fetchall()
        if not rows:
            return 0.5, 0
        total = len(rows)
        win_rate = sum(1 for r in rows if r[0] == 1) / total
        return float(win_rate), total
    except Exception:
        return 0.5, 0

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

_get_lightgbm_model = _get_next_day_lgb_model

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


_KRONOS_MODEL_FN = None
def _get_kronos_predictor_fn():
    global _KRONOS_MODEL_FN
    if _KRONOS_MODEL_FN is None:
        try:
            from praecursor.ml.kronos_forecaster import predict_next_candle
            _KRONOS_MODEL_FN = predict_next_candle
        except Exception as e:
            logger.debug(f"Failed to load Kronos forecaster: {e}")
            _KRONOS_MODEL_FN = False
    return _KRONOS_MODEL_FN if _KRONOS_MODEL_FN is not False else None


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


def _calculate_structural_levels(
    latest_close: float,
    stock_obj: Any,
    values: dict[str, Any],
    symbol: str,
) -> tuple[float, float, str, str]:
    """
    Derive price-action and structure-based Target and Stop-Loss levels.
    Uses real support/resistance pivots, breakout levels, dynamic EMAs, and swing pivots.
    """
    atr14 = values.get("ATR14", float("nan"))
    if _missing(atr14) or atr14 <= 0:
        atr14 = latest_close * 0.04

    # -------------------------------------------------------------
    # 1. Structural Stop Loss Determination
    # -------------------------------------------------------------
    stop_candidates: list[tuple[float, str]] = []

    # A. Recent Swing Low (last 3-5 bars)
    if stock_obj is not None and hasattr(stock_obj, "history") and len(stock_obj.history) >= 5:
        recent_bars = stock_obj.history[-5:]
        recent_low = min(b.low for b in recent_bars)
        if 0 < recent_low < latest_close:
            lvl = recent_low * 0.995
            stop_candidates.append((lvl, f"0.5% below 5-day swing low ({recent_low:.2f})"))

    # B. Dynamic EMA20 Support
    ema20 = values.get("EMA20", float("nan"))
    if not _missing(ema20) and 0 < ema20 < latest_close:
        lvl = ema20 * 0.990
        stop_candidates.append((lvl, f"1.0% below dynamic EMA20 support ({ema20:.2f})"))

    # C. Breakout Level Retest (Prior 20-day High)
    if stock_obj is not None and hasattr(stock_obj, "history") and len(stock_obj.history) >= 20:
        prior_20_high = max(b.high for b in stock_obj.history[-21:-1])
        if 0 < prior_20_high < latest_close:
            lvl = prior_20_high * 0.990
            stop_candidates.append((lvl, f"below 20-day breakout retest pivot ({prior_20_high:.2f})"))

    # D. Lower Keltner Support
    keltner_lower = values.get("KeltnerLower", float("nan"))
    if not _missing(keltner_lower) and 0 < keltner_lower < latest_close:
        stop_candidates.append((keltner_lower, f"at Lower Keltner channel boundary ({keltner_lower:.2f})"))

    # Pick the most proximate valid structural stop within a realistic risk envelope (2.0% - 7.5%)
    valid_stops = [
        (lvl, desc) for lvl, desc in stop_candidates
        if 0.020 <= (latest_close - lvl) / latest_close <= 0.075
    ]

    if valid_stops:
        stop_price, stop_desc = max(valid_stops, key=lambda item: item[0])
    else:
        # Fallback to 1.0x ATR14 disciplined stop
        stop_price = latest_close - (1.0 * atr14)
        stop_pct = (latest_close - stop_price) / latest_close if latest_close > 0 else 0.04
        stop_pct = max(0.025, min(stop_pct, 0.065))
        stop_price = latest_close * (1.0 - stop_pct)
        stop_desc = f"1.0x ATR14 volatility floor"

    # -------------------------------------------------------------
    # 2. Structural Target Determination
    # -------------------------------------------------------------
    target_candidates: list[tuple[float, str]] = []

    # A. 52-Week / 250-Day Major Resistance High
    close_high_250 = values.get("CloseHigh250", float("nan"))
    if not _missing(close_high_250) and close_high_250 > latest_close:
        dist = (close_high_250 - latest_close) / latest_close
        if 0.03 <= dist <= 0.15:
            target_candidates.append((close_high_250, f"at 250-day resistance pivot ({close_high_250:.2f})"))

    # B. Upper Volatility Band (Bollinger / Keltner)
    upper_band = values.get("BollingerUpper", values.get("KeltnerUpper", float("nan")))
    if not _missing(upper_band) and upper_band > latest_close:
        dist = (upper_band - latest_close) / latest_close
        if 0.03 <= dist <= 0.15:
            target_candidates.append((upper_band, f"at Upper Volatility Band expansion ({upper_band:.2f})"))

    # C. High Volume Node / VPOC Extension (if above close)
    vpoc_price = values.get("VPOC_Price", float("nan"))
    if not _missing(vpoc_price) and vpoc_price > latest_close:
        dist = (vpoc_price - latest_close) / latest_close
        if 0.03 <= dist <= 0.12:
            target_candidates.append((vpoc_price, f"at Volume Point of Control (VPOC: {vpoc_price:.2f})"))

    # D. Measured Breakout Projection (Consolidation Base Height + Close)
    if stock_obj is not None and hasattr(stock_obj, "history") and len(stock_obj.history) >= 20:
        base_low = min(b.low for b in stock_obj.history[-20:])
        base_high = max(b.high for b in stock_obj.history[-20:])
        base_height = base_high - base_low
        if 0 < base_height < latest_close * 0.20:
            measured_target = latest_close + (base_height * 0.618)
            dist = (measured_target - latest_close) / latest_close
            if 0.04 <= dist <= 0.14:
                target_candidates.append((measured_target, f"at 61.8% Fibonacci base expansion ({measured_target:.2f})"))

    # Pick the best valid structural target
    valid_targets = [
        (lvl, desc) for lvl, desc in target_candidates
        if 0.035 <= (lvl - latest_close) / latest_close <= 0.15
    ]

    if valid_targets:
        target_price, target_desc = min(valid_targets, key=lambda item: item[0])
    else:
        # Fallback to 1.5x ATR14 measured move
        target_price = latest_close + (1.5 * atr14)
        target_pct = (target_price - latest_close) / latest_close if latest_close > 0 else 0.06
        target_pct = max(0.040, min(target_pct, 0.120))
        target_price = latest_close * (1.0 + target_pct)
        target_desc = f"1.5x ATR14 measured momentum extension"

    # Clamp by stock-specific Circuit Breaker if necessary
    cb_limit = _CIRCUIT_BREAKER_LIMITS.get(symbol, _DEFAULT_CIRCUIT_BREAKER)
    max_price = latest_close * (1.0 + (cb_limit * 0.975))
    if target_price > max_price:
        target_price = max_price
        target_desc = f"clamped by EGX daily limit ceiling ({cb_limit*100:.0f}%)"

    return target_price, stop_price, target_desc, stop_desc


@dataclass(frozen=True)
class NextDayPrediction:
    """Next-session breakout/follow-through assessment."""

    score: float
    label: str
    reasons: list[str]
    latest_close: float = 0.0
    target_price: float = 0.0          # Target 1 (Take-profit 50% scale-out)
    target_price_2: float = 0.0        # Target 2 (Runner TP - exponential breakout)
    stop_loss_price: float = 0.0       # Initial dynamic EWMA stop
    trailing_stop_price: float = 0.0   # Breakeven stop anchor once TP1 hit
    kelly_fraction: float = 0.0
    liquidity_tier: str = "MODERATE"   # HIGH, MODERATE, THIN
    fill_feasibility: str = "Standard Execution"

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
    if ticker_win_rate < 0.3 and ticker_win_rate >= 0.0:
        reasons.append(f"[BACKTEST REJECTION] Historically poor win-rate ({ticker_win_rate*100:.0f}%).")
        ticker_history_penalty = 10.0

    breakout20 = values.get("Breakout20", float("nan"))
    breakout50 = values.get("Breakout50", float("nan"))
    volume_confirmed_breakout = values.get("VolumeConfirmedBreakout", float("nan"))
    rsi14 = values.get("RSI14", float("nan"))

    # ML Ensemble Inference (using exact 35 trained features)
    features_orig = [
        "RSI14", "RelVolume20", "MACDHistogram", "Momentum20", 
        "Breakout20", "Breakout50", "RSIRebound", "EMA20Reclaim", 
        "MACDHistogramImprovement", "VolumeSpikeFromWeakness", "Momentum5", "BBW20",
        "MTF_Trend", "VPOC_Distance", "ADX14", "ROC10", "StochRSI", "VWAPMom10",
        "AvgTurnover20", "ClosedAtLimitUp", "ATRPercent14",
        "OpportunityScorePct", "NearCloseHigh250Percent", "CMF20", "MFI14",
        "RS_vs_EGX30_50", "VolumeConfirmedBreakout", "WilliamsR14",
        "KCSqueeze20", "Ichimoku_Score", "ElderRay_Score",
        # v6.1 Next-Day Alpha Features
        "ClosingAggression", "NR7_Compression", "VSA_Absorption", "SectorSpillover",
    ]
    features_csv = [
        "rsi14", "rel_volume20", "macd_histogram", "momentum20", "breakout20", "breakout50",
        "rsi_rebound", "ema20_reclaim", "macd_histogram_improvement", "volume_spike_from_weakness", "momentum5", "bbw20",
        "mtf_trend", "vpoc_distance", "adx14", "roc10", "stoch_rsi", "vwap_mom10",
        "avg_turnover_20", "closed_at_limit_up", "atr_pct14",
        "opp_score_pct", "near_high250_pct", "cmf20", "mfi14",
        "rs_vs_index", "vol_confirmed_breakout", "williams_r14",
        "kc_squeeze20", "ichimoku_score", "elder_ray_score",
        # v6.1 Next-Day Alpha Features
        "closing_aggression", "nr7_compression", "vsa_absorption", "sector_spillover",
    ]
    
    xgb_prob = None
    lgb_prob = None
    row_data = {}
    for csv_name, orig_name in zip(features_csv, features_orig):
        if orig_name == "OpportunityScorePct":
            val = base_score
        else:
            val = values.get(orig_name, 0.0)
            
        if val is None or (isinstance(val, float) and val != val):
            val = 0.0
        if isinstance(val, dict):
            val = val.get("VPOC_Distance_Pct", 0.0) if "VPOC_Distance_Pct" in val else 0.0
            
        row_data[csv_name] = float(val)

    if pd is not None and np is not None:
        try:
            df = pd.DataFrame([row_data])
            X_arr = df[features_csv].values
            
            xgb_model = _get_next_day_model()
            if xgb_model is not None:
                xgb_prob = float(xgb_model.predict_proba(X_arr)[0][1])
                
            lgb_model = _get_next_day_lgb_model()
            if lgb_model is not None:
                lgb_prob = float(lgb_model.predict(X_arr)[0])
        except Exception as e:
            logger.debug(f"ML inference error: {e}")

    meta = _get_next_day_meta()
    xgb_w = meta.get("xgb_weight", 0.6)
    lgb_w = meta.get("lgb_weight", 0.4)

    if xgb_prob is not None and lgb_prob is not None:
        if abs(xgb_prob - lgb_prob) > 0.30:
            score -= 5.0
            reasons.append(f"[MODEL DISAGREEMENT] XGB and LGB differ by {abs(xgb_prob - lgb_prob)*100:.0f}% — reduced confidence")
        ensemble_prob = (xgb_prob ** xgb_w * lgb_prob ** lgb_w) ** (1.0 / (xgb_w + lgb_w))
        ml_bonus = (ensemble_prob - 0.5) * 20.0
        score += ml_bonus
        reasons.append(f"Ensemble Model Probability: {ensemble_prob*100:.1f}% (Bonus: {ml_bonus:+.1f})")
    elif xgb_prob is not None:
        ml_bonus = (xgb_prob - 0.5) * 20.0
        score += ml_bonus
        reasons.append(f"XGBoost Model Probability: {xgb_prob*100:.1f}% (Bonus: {ml_bonus:+.1f})")
    elif lgb_prob is not None:
        ml_bonus = (lgb_prob - 0.5) * 20.0
        score += ml_bonus
        reasons.append(f"LightGBM Model Probability: {lgb_prob*100:.1f}% (Bonus: {ml_bonus:+.1f})")

    from praecursor.scoring.regime import MarketRegimeModel
    regime_info = MarketRegimeModel().get_latest_regime()
    regime = regime_info.get("regime", "Unknown")
    if "Bear" in regime:
        score *= 0.93
        reasons.append(f"Regime {regime}: Defensive bear market dampener applied")
    elif "Bull" in regime:
        score *= 1.07
        reasons.append(f"Regime {regime}: Soft bull market bonus applied")

    whipsaw_multiplier = _get_whipsaw_penalty(symbol)
    if whipsaw_multiplier < 1.0:
        reasons.append(f"[WHIPSAW] {symbol} has failed recent breakout attempts - soft penalty applied")

    vpoc_overhead_penalty = 0.0
    vpoc_dist = values.get("VPOC_Distance_Pct", float("nan"))
    if not _missing(vpoc_dist) and 0.5 < vpoc_dist < 4.0:
        vpoc_overhead_penalty = 8.0
        reasons.append(f"Major overhead volume resistance near {vpoc_dist:+.1f}%")

    gap_blackout_penalty = 0.0
    if stock_obj is not None and hasattr(stock_obj, "history") and len(stock_obj.history) >= 2:
        prev_bar = stock_obj.history[-2]
        curr_bar = stock_obj.history[-1]
        gap_pct = abs(curr_bar.open - prev_bar.close) / prev_bar.close * 100.0 if prev_bar.close > 0 else 0.0
        if gap_pct > 8.0 and curr_bar.volume == 0:
            gap_blackout_penalty = 10.0
            reasons.append(f"Corporate action blackout / non-organic gap of {gap_pct:.1f}%")

    turnover20 = values.get("Turnover20", float("nan"))
    atr_pct = values.get("ATRPercent14", float("nan"))
    if not _missing(atr_pct):
        if atr_pct > 5.0:
            reasons.append(f"High volatility (ATR {atr_pct:.1f}% > 5.0%) with acceptable liquidity: Explosive setup")
        elif atr_pct < 2.5:
            score -= 10.0
            reasons.append(f"Low volatility (ATR {atr_pct:.1f}% < 2.5%): Deprioritized for rapid next-day moves")

        if not _missing(turnover20) and turnover20 > 100_000_000 and atr_pct < 4.0:
            score -= 15.0
            reasons.append(f"Heavy mega-cap (Turnover > 100M) lacks volatility for fast intraday swings")

    # v6.1 Next-Day Alpha Hunters: MOC Aggression, Volatility Compression, VSA Absorption, Sector Spillover
    closing_agg = values.get("ClosingAggression", 0.0)
    if not _missing(closing_agg) and closing_agg >= 75.0:
        moc_bonus = min(8.0, (closing_agg - 70.0) * 0.25)
        score += moc_bonus
        reasons.append(f"[MOC AGGRESSION] Institutional closing sweep ({closing_agg:.1f}%) into the bell (Bonus: +{moc_bonus:.1f})")

    nr7_comp = values.get("NR7_Compression", 0.0)
    if not _missing(nr7_comp) and nr7_comp >= 50.0:
        nr7_bonus = min(6.0, (nr7_comp - 40.0) * 0.15)
        score += nr7_bonus
        reasons.append(f"[VOLATILITY COIL] NR7 / Inside Day compression detected (Bonus: +{nr7_bonus:.1f})")

    vsa_abs = values.get("VSA_Absorption", 0.0)
    if not _missing(vsa_abs) and vsa_abs >= 50.0:
        vsa_bonus = min(5.0, (vsa_abs - 40.0) * 0.12)
        score += vsa_bonus
        reasons.append(f"[VSA ABSORPTION] Institutional supply absorption at resistance (Bonus: +{vsa_bonus:.1f})")

    sec_spill = values.get("SectorSpillover", 0.0)
    if not _missing(sec_spill) and sec_spill >= 75.0:
        score += 3.0
        reasons.append("[SECTOR SPILLOVER] Sector momentum spillover confirmed (Bonus: +3.0)")

    # v6.1 Artificial Cross-Trade / Penny Noise Filter
    if stock_obj is not None and hasattr(stock_obj, "history") and len(stock_obj.history) >= 5:
        latest_bar = stock_obj.history[-1]
        spread_pct = (latest_bar.high - latest_bar.low) / latest_bar.close * 100.0 if latest_bar.close > 0 else 1.0
        rel_v = values.get("RelVolume20", 1.0)
        t_over = values.get("AvgTurnover20", 10_000_000)
        if spread_pct < 0.35 and rel_v > 2.5 and t_over < 1_500_000:
            score -= 15.0
            reasons.append("[CROSS-TRADE FILTER] Zero-spread volume anomaly flagged (likely artificial cross trade)")
            
    score = max(0.0, min(score, 100.0))
    score *= whipsaw_multiplier
    score = max(0.0, score - vpoc_overhead_penalty)
    score = max(0.0, score - gap_blackout_penalty)
    
    latest_close = opportunity_score.latest_close

    # Step 1: True Technical & Structural Target and Stop-Loss Determination
    target_price, stop_loss_price, target_desc, stop_desc = _calculate_structural_levels(
        latest_close=latest_close,
        stock_obj=stock_obj,
        values=values,
        symbol=symbol,
    )
    target_price_2 = target_price
    trailing_stop_price = latest_close

    target_pct = (target_price - latest_close) / latest_close * 100.0 if latest_close > 0 else 0.0
    stop_pct = (latest_close - stop_loss_price) / latest_close * 100.0 if latest_close > 0 else 0.0
    reasons.append(f"Target placed at {target_price:.2f} (+{target_pct:.1f}%) {target_desc}")
    reasons.append(f"Stop Loss placed at {stop_loss_price:.2f} (-{stop_pct:.1f}%) {stop_desc}")

    # Step 2: Kronos Financial Candlestick Foundation Model Alignment (v6.3 Institutional Alpha)
    is_breakout_setup = (breakout20 == 1.0 or breakout50 == 1.0 or volume_confirmed_breakout == 1.0)
    is_candidate_setup = (score >= 68.0 and base_score >= 60.0)

    predict_kronos_fn = _get_kronos_predictor_fn()
    if predict_kronos_fn is not None and (is_breakout_setup and is_candidate_setup):
        try:
            history_df = None
            if stock_obj is not None and hasattr(stock_obj, "history") and len(stock_obj.history) >= 20:
                history_df = pd.DataFrame([
                    {
                        "trade_date": b.date.strftime("%Y-%m-%d") if hasattr(b.date, "strftime") else str(b.date),
                        "open": float(b.open),
                        "high": float(b.high),
                        "low": float(b.low),
                        "close": float(b.close),
                        "volume": float(b.volume),
                    }
                    for b in stock_obj.history
                ])
            kronos_pred = predict_kronos_fn(symbol, history_df=history_df)
            if kronos_pred is not None and kronos_pred.is_valid:
                if kronos_pred.predicted_high >= target_price or (kronos_pred.direction == "BULLISH" and kronos_pred.expected_return_pct > 0):
                    score += 3.0
                    reasons.append(
                        f"[KRONOS FOUNDATION AI] Forecasts Bullish candle expansion "
                        f"(Predicted High: {kronos_pred.predicted_high:.3f}, +{kronos_pred.expected_return_pct:.1f}%)"
                    )
                else:
                    reasons.append(
                        f"[KRONOS FOUNDATION AI CAUTION] Model forecasts muted/bearish next-day candle "
                        f"(Predicted Close: {kronos_pred.predicted_close:.3f}, {kronos_pred.expected_return_pct:+.1f}%)"
                    )
        except Exception as e:
            logger.debug(f"Kronos prediction error for {symbol}: {e}")

    # Step 3: EGX Liquidity & Fill Feasibility Analysis
    turnover_val = values.get("AvgTurnover20", 0.0)
    if _missing(turnover_val) or float(turnover_val) <= 0:
        avg_vol = values.get("AvgVolume20", 0.0)
        turnover_val = (float(avg_vol) * latest_close) if not _missing(avg_vol) and latest_close > 0 else 0.0
    else:
        turnover_val = float(turnover_val)

    closed_at_limit_up = values.get("ClosedAtLimitUp", 0.0)
    if turnover_val >= 10_000_000:
        liquidity_tier = "HIGH"
        fill_feasibility = "High Liquidity (>10M EGP/day - Instant Fill)"
    elif turnover_val >= 2_000_000:
        liquidity_tier = "MODERATE"
        fill_feasibility = "Moderate Liquidity (2M-10M EGP/day - Limit Orders)"
    else:
        liquidity_tier = "THIN"
        fill_feasibility = "Thin Liquidity (<2M EGP/day - Slippage Risk)"

    if closed_at_limit_up == 1.0:
        reasons.append("[CIRCUIT BREAKER LOCK] Closed at daily ceiling (+10%/+20%). Expect Sunday opening queue.")

    from praecursor.scoring.regime import MarketRegimeModel
    regime_info = MarketRegimeModel().get_latest_regime()
    regime_name = regime_info.get("regime", "Unknown")

    # Step 4: Half-Kelly Position Sizing with Conservative Constraints
    kelly_fraction = 0.0
    # Map calibrated score (50-75%) to realistic win probability (50-62%)
    win_prob = max(0.40, min(0.50 + max(0.0, score - 50.0) * 0.005, 0.62))
    target_pct = (target_price - latest_close) / latest_close if latest_close > 0 else 0.0
    stop_pct = (latest_close - stop_loss_price) / latest_close if latest_close > 0 else 0.0
    if target_pct > 0 and stop_pct > 0:
        b = target_pct / stop_pct  # Reward-to-risk ratio
        full_kelly = win_prob - ((1.0 - win_prob) / b)
        half_kelly = full_kelly * 0.5  # Standard institutional Half-Kelly
        
        regime_mult = 1.0
        if "Bull Trend" in regime_name:
            regime_mult = 1.2
        elif "Sideways Chop" in regime_name:
            regime_mult = 0.8
        elif "Bear Volatile" in regime_name:
            regime_mult = 0.5
        elif "Bear Trend" in regime_name:
            regime_mult = 0.6
        elif "Bull Volatile" in regime_name:
            regime_mult = 0.9
            
        adjusted_kelly = half_kelly * regime_mult
        kelly_fraction = max(0.02, min(adjusted_kelly, 0.25))
        
        if regime_mult != 1.0:
            reasons.append(f"Kelly fraction adjusted by {regime_mult}x due to {regime_name} regime.")
            
    rr_ratio = (target_pct / stop_pct) if stop_pct > 0 else 1.5
    label = _label(
        score=score,
        rsi14=rsi14,
        breakout20=breakout20,
        breakout50=breakout50,
        volume_confirmed_breakout=volume_confirmed_breakout,
        consensus_accepted=consensus_accepted,
        opp_score=opportunity_score.score_percent,
        regime=regime_name,
        kelly=kelly_fraction,
        rr_ratio=rr_ratio,
        latest_close=latest_close,
        turnover=turnover_val,
    )

    if "Candidate" in label or "Watch" in label:
        ml_desc = ""
        prob_val = ensemble_prob if 'ensemble_prob' in locals() and ensemble_prob is not None else (xgb_prob if 'xgb_prob' in locals() and xgb_prob is not None else None)
        if prob_val is not None:
            if prob_val >= 0.5:
                ml_desc = f", ML confirms ({prob_val:.1%})"
            else:
                ml_desc = f", ML cautious ({prob_val:.1%})"
        summary = f"Analysis for {symbol}: Strong setup based on Opportunity Score {base_score:.1f}%{ml_desc}, in {regime_name} regime"
        reasons.insert(0, summary)
    elif "Illiquid Micro-Penny" in label:
        reasons.insert(0, f"Analysis for {symbol}: Filtered out due to micro-penny price (<0.20 EGP) or insufficient daily liquidity (<250k EGP)")
    elif "Low Confidence" in label:
        reasons.insert(0, f"Analysis for {symbol}: Data unverified across consensus sources (Low Confidence)")
    elif "Poor Reward/Risk" in label:
        reasons.insert(0, f"Analysis for {symbol}: Unfavorable reward-to-risk geometry (Negative Expectancy)")
    else:
        reasons.insert(0, f"Analysis for {symbol}: Insufficient technical edge or negative regime conditions")

    if not reasons or len(reasons) == 1:
        reasons.append("no strong next-day breakout/follow-through pattern detected")

    return NextDayPrediction(
        score=score, 
        label=label, 
        reasons=reasons,
        latest_close=latest_close,
        target_price=target_price,
        target_price_2=target_price_2,
        stop_loss_price=stop_loss_price,
        trailing_stop_price=trailing_stop_price,
        kelly_fraction=kelly_fraction,
        liquidity_tier=liquidity_tier,
        fill_feasibility=fill_feasibility,
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
    rr_ratio: float = 1.0,
    latest_close: float = 1.0,
    turnover: float = 1_000_000.0,
) -> str:
    if not consensus_accepted:
        return "Low Confidence"
    
    if latest_close < 0.20 or turnover < 250_000:
        return "Avoid Tomorrow (Illiquid Micro-Penny)"
    
    if opp_score < 30.0:
        return "Avoid Tomorrow"
    
    if kelly <= 0.0 or rr_ratio < 0.8:
        return "Avoid Tomorrow (Poor Reward/Risk)"
    
    # Dynamic calibrated thresholds matching post-calibration score distribution (50-75%)
    if "Bull" in regime:
        candidate_threshold = 60.0
        watch_threshold = 50.0
    elif "Bear" in regime:
        candidate_threshold = 66.0
        watch_threshold = 56.0
    else:
        candidate_threshold = 62.0
        watch_threshold = 52.0
    
    is_breakout = breakout20 == 1.0 and breakout50 == 1.0
    is_volume_confirmed = volume_confirmed_breakout == 1.0
    is_overextended = not _missing(rsi14) and rsi14 > 75.0
    
    # Breakout candidate requires solid score, breakout pattern, volume confirmation, and good R:R (>= 1.20x)
    if score >= candidate_threshold + 6.0 and is_breakout and is_volume_confirmed and rr_ratio >= 1.20:
        if is_overextended:
            return "Next-Day Breakout Candidate - Extended"
        return "Next-Day Breakout Candidate"
    
    if score >= candidate_threshold:
        return "High-Priority Next-Day Watch"
    
    if score >= watch_threshold:
        return "Watchlist Tomorrow"
    
    return "Avoid Tomorrow"

def _missing(value) -> bool:
    if value is None:
        return True
    try:
        return isnan(float(value))
    except (ValueError, TypeError):
        return True
