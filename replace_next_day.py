import re

with open("src/praecursor/scoring/next_day.py", "r") as f:
    content = f.read()

# Replace _label function
label_pattern = re.compile(r"def _label\(.*?\)\s*->\s*str:.*?(?=def _missing)", re.DOTALL)
new_label = """def _label(
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
        candidate_threshold = 55
        watch_threshold = 45
    elif "Bear" in regime:
        candidate_threshold = 65
        watch_threshold = 55
    else:
        candidate_threshold = 60
        watch_threshold = 50
    
    is_breakout = breakout20 == 1.0 and breakout50 == 1.0
    is_volume_confirmed = volume_confirmed_breakout == 1.0
    is_overextended = not _missing(rsi14) and rsi14 > 75
    
    if score >= candidate_threshold + 15 and is_breakout and is_volume_confirmed:
        if is_overextended:
            return "Next-Day Breakout Candidate - Extended"
        return "Next-Day Breakout Candidate"
    
    if score >= candidate_threshold:
        return "High-Priority Next-Day Watch"
    
    if score >= watch_threshold:
        return "Watchlist Tomorrow"
    
    return "Avoid Tomorrow"

"""
content = label_pattern.sub(new_label, content)

# Replace calculate_next_day_prediction function
calc_pattern = re.compile(r"def calculate_next_day_prediction\(.*?\)\s*->\s*NextDayPrediction:.*?def _label\(", re.DOTALL)
new_calc = """def calculate_next_day_prediction(
    opportunity_score: OpportunityScore,
    consensus_accepted: bool = True,
    consensus_confidence: float = 40.0,
    data_quality_score: float = 100.0,
) -> NextDayPrediction:
    \"\"\"Calculate next-session breakout/follow-through prediction.\"\"\"
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
        reasons.append(f"[WHIPSAW] {symbol} has failed recent breakout attempts — soft penalty applied")

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
    if not _missing(news_sentiment) and not _missing(relative_vol_val):
        if relative_vol_val >= 2.5 and news_sentiment <= 0:
            reasons.append("[CATALYST REJECTION] Massive volume spike but no positive news catalyst detected.")
            no_news_penalty = 25.0

    day_of_week = values.get("DayOfWeek", float("nan"))
    weekend_risk_penalty = 0.0
    if not _missing(day_of_week) and day_of_week == 3.0: 
        if relative_vol_val < 1.5:
            reasons.append("[WEEKEND RISK] Late-week breakout lacking massive volume. High risk of decay.")
            weekend_risk_penalty = 5.0

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
            "Momentum1", "RSISlope3", "ConsecutiveGreen", "DayOfWeek",
            "hurst_exponent", "news_sentiment", "tft_prob", "gnn_spillover_score"
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
            "momentum1", "rsi_slope3", "consecutive_green", "day_of_week",
            "hurst_exponent", "news_sentiment", "tft_prob", "gnn_spillover_score"
        ]
        
        flat_values = {}
        for k, v in values.items():
            if isinstance(v, dict):
                for sub_k, sub_v in v.items():
                    flat_values[sub_k] = sub_v
            else:
                flat_values[k] = v
        row_data = {csv_name: flat_values.get(orig_name, 0.0) for csv_name, orig_name in zip(csv_features, features)}
        for k, v in row_data.items():
            if v != v:
                row_data[k] = 0.0
        df = pd.DataFrame([row_data])
        X_arr = df[csv_features].values
        
        ml_bonus = 0.0
        try:
            prob = model.predict_proba(X_arr)[0][1]
            xgb_bonus = (prob - 0.5) * 30.0
            ml_bonus += xgb_bonus
            reasons.append(f"XGBoost Model Probability: {prob:.1%} (Bonus: {xgb_bonus:+.1f})")
        except Exception as e:
            pass
            
        lgb_model = _get_next_day_lgb_model()
        if lgb_model is not None:
            try:
                lgb_prob = lgb_model.predict(X_arr)[0]
                lgb_bonus = (lgb_prob - 0.5) * 20.0
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
    score = max(0.0, score - no_news_penalty)
    score = max(0.0, score - weekend_risk_penalty)
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
    win_prob = score / 100.0
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

def _label("""
content = calc_pattern.sub(new_calc, content)

with open("src/praecursor/scoring/next_day.py", "w") as f:
    f.write(content)
