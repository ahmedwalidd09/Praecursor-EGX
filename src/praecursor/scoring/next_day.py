from dataclasses import dataclass
from math import isnan
from typing import Any
from praecursor.scoring.opportunity_score import OpportunityScore

# Conservative target cap; exchange-specific limits require a verified instrument feed.
_CIRCUIT_BREAKER_LIMITS = {}
_DEFAULT_CIRCUIT_BREAKER = 0.20


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
    if latest_close <= 0 or _missing(latest_close):
        return 0.0, 0.0, "Invalid close price", "Invalid close price"

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
    vpoc_value = values.get("VPOC_Distance", {})
    vpoc_price = vpoc_value.get("VPOC_Price", float("nan")) if isinstance(vpoc_value, dict) else float("nan")
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

    if stop_price <= 0 or stop_price >= latest_close:
        stop_price = latest_close * 0.96
        stop_desc = "4.0% protective stop floor"
    if target_price <= latest_close:
        target_price = latest_close * 1.05
        target_desc = "5.0% baseline technical target"

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
    probability: float | None = None
    model_version: str = "technical-only"
    fill_feasibility: str = "Standard Execution"

    @property
    def reasons_text(self) -> str:
        return "; ".join(self.reasons)


def calculate_next_day_prediction(
    opportunity_score: OpportunityScore,
    consensus_accepted: bool = False,
    consensus_confidence: float = 0.0,
    data_quality_score: float = 0.0,
) -> NextDayPrediction:
    """Calculate next-session breakout/follow-through prediction."""
    values = opportunity_score.indicator_values
    symbol = opportunity_score.symbol
    reasons: list[str] = []
    
    base_score = opportunity_score.score_percent
    score = base_score
    reasons.append(f"Base Opportunity Score: {base_score:.1f}%")

    stock_obj = getattr(opportunity_score, "stock", None)
    
    # Legacy HMM/ticker heuristics have no point-in-time validation contract.
    whipsaw_multiplier = 1.0
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

    breakout20 = values.get("Breakout20", float("nan"))
    breakout50 = values.get("Breakout50", float("nan"))
    volume_confirmed_breakout = values.get("VolumeConfirmedBreakout", float("nan"))
    rsi14 = values.get("RSI14", float("nan"))

    from praecursor.ml.prediction import predict_validated
    session = stock_obj.history[-1].date.date().isoformat() if stock_obj and stock_obj.history else None
    calibrated_probability, meta = predict_validated(values, base_score, "next_day", session)
    compatible_model = calibrated_probability is not None
    if compatible_model:
        reasons.append(f"Estimated next-session target-touch probability: {calibrated_probability:.1%}")

    regime_info = getattr(stock_obj, "market_context", {})
    regime = regime_info.get("regime", "Unknown")
    if "Bear" in regime:
        score *= 0.93
        reasons.append(f"Regime {regime}: Defensive bear market dampener applied")
    elif "Bull" in regime:
        score *= 1.07
        reasons.append(f"Regime {regime}: Soft bull market bonus applied")

    vpoc_dist = values.get("VPOC_Distance_Pct", float("nan"))
    if not _missing(vpoc_dist) and 0.5 < vpoc_dist < 4.0:
        vpoc_overhead_penalty += 8.0
        reasons.append(f"Major overhead volume resistance near {vpoc_dist:+.1f}%")

    if stock_obj is not None and hasattr(stock_obj, "history") and len(stock_obj.history) >= 2:
        prev_bar = stock_obj.history[-2]
        curr_bar = stock_obj.history[-1]
        gap_pct = abs(curr_bar.open - prev_bar.close) / prev_bar.close * 100.0 if prev_bar.close > 0 else 0.0
        if gap_pct > 8.0 and curr_bar.volume == 0:
            gap_blackout_penalty = max(gap_blackout_penalty, 10.0)
            reasons.append(f"Corporate action blackout / non-organic gap of {gap_pct:.1f}%")

    turnover20 = values.get("AvgTurnover20", float("nan"))
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
        reasons.append(f"[DAILY CLOSE PROXY] Close-location strength ({closing_agg:.1f}%) (daily OHLCV, not observed order flow; Bonus: +{moc_bonus:.1f})")

    nr7_comp = values.get("NR7_Compression", 0.0)
    if not _missing(nr7_comp) and nr7_comp >= 50.0:
        nr7_bonus = min(6.0, (nr7_comp - 40.0) * 0.15)
        score += nr7_bonus
        reasons.append(f"[VOLATILITY COIL] NR7 / Inside Day compression detected (Bonus: +{nr7_bonus:.1f})")

    vsa_abs = values.get("VSA_Absorption", 0.0)
    if not _missing(vsa_abs) and vsa_abs >= 50.0:
        vsa_bonus = min(5.0, (vsa_abs - 40.0) * 0.12)
        score += vsa_bonus
        reasons.append(f"[VOLUME/RANGE PROXY] High-volume price compression (Bonus: +{vsa_bonus:.1f})")

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

    # Kronos remains available through tools/predict_kronos.py for research.
    # Production ranking requires held-out evidence before adding its forecasts.

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
        fill_feasibility = "High historical turnover (>10M EGP/day); fills depend on order size and spread"
    elif turnover_val >= 2_000_000:
        liquidity_tier = "MODERATE"
        fill_feasibility = "Moderate Liquidity (2M-10M EGP/day - Limit Orders)"
    else:
        liquidity_tier = "THIN"
        fill_feasibility = "Thin Liquidity (<2M EGP/day - Slippage Risk)"

    if closed_at_limit_up == 1.0:
        reasons.append("[CIRCUIT BREAKER LOCK] Closed at daily ceiling (+10%/+20%). Opening fill may be unavailable.")

    regime_info = getattr(stock_obj, "market_context", {})
    regime_name = regime_info.get("regime", "Unknown")

    # Target-touch probability does not establish executable trade win probability.
    # Do not fabricate a Kelly fraction from a technical score or target-touch model.
    kelly_fraction = 0.0
    if calibrated_probability is not None:
        score = calibrated_probability * 100.0

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

    if compatible_model and consensus_accepted and data_quality_score >= 80 and turnover_val >= 250_000 and latest_close >= .2:
        label = "Next-Day Candidate" if calibrated_probability >= meta["threshold"] else "Watchlist Tomorrow"
    if data_quality_score < 80:
        label = "Insufficient History Quality"
        reasons.insert(0, "Insufficient validated history or session quality")
    if calibrated_probability is None:
        reasons.append("Technical setup only; no validated target probability or Kelly allocation available")
        reasons.append(meta.get("reason", "Model validation unavailable"))

    if not reasons or len(reasons) == 1:
        reasons.append("no strong next-day breakout/follow-through pattern detected")

    return NextDayPrediction(
        score=max(0.0, min(score, 100.0)),
        probability=calibrated_probability,
        model_version=meta.get("model_version", "technical-only") if compatible_model else "technical-only",
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
        return "Unconfirmed Watchlist"
    
    if _missing(latest_close) or latest_close < 0.20 or _missing(turnover) or turnover < 250_000:
        return "Avoid Tomorrow (Illiquid Micro-Penny)"
    
    if opp_score < 30.0:
        return "Avoid Tomorrow"
    
    if rr_ratio < 0.8:
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
