"""One versioned feature contract for training, replay and live prediction."""
from math import isfinite

FEATURE_VERSION = "3"
INDICATOR_TO_FEATURE = {
    "RSI14": "rsi14", "RelVolume20": "rel_volume20",
    "MACDHistogram": "macd_histogram", "Momentum20": "momentum20",
    "Breakout20": "breakout20", "Breakout50": "breakout50",
    "RSIRebound": "rsi_rebound", "EMA20Reclaim": "ema20_reclaim",
    "MACDHistogramImprovement": "macd_histogram_improvement",
    "VolumeSpikeFromWeakness": "volume_spike_from_weakness",
    "Momentum5": "momentum5", "BBW20": "bbw20", "MTF_Trend": "mtf_trend",
    "VPOC_Distance": "vpoc_distance", "ADX14": "adx14", "ROC10": "roc10",
    "StochRSI": "stoch_rsi", "VWAPMom10": "vwap_mom10",
    "AvgTurnover20": "avg_turnover_20", "ClosedAtLimitUp": "closed_at_limit_up",
    "ATRPercent14": "atr_pct14", "OpportunityScorePct": "opp_score_pct",
    "NearCloseHigh250Percent": "near_high250_pct", "CMF20": "cmf20",
    "MFI14": "mfi14", "RS_vs_EGX30_50": "rs_vs_index",
    "VolumeConfirmedBreakout": "vol_confirmed_breakout", "WilliamsR14": "williams_r14",
    "KCSqueeze20": "kc_squeeze20", "Ichimoku_Score": "ichimoku_score",
    "ElderRay_Score": "elder_ray_score", "ClosingAggression": "closing_aggression",
    "NR7_Compression": "nr7_compression", "VSA_Absorption": "vsa_absorption",
    "SectorSpillover": "sector_spillover",
}
FEATURES = list(INDICATOR_TO_FEATURE.values())


def feature_row(values, opportunity_score):
    """Missing measurements stay missing; zero is a real measured value."""
    row = {}
    for indicator, name in INDICATOR_TO_FEATURE.items():
        value = opportunity_score if indicator == "OpportunityScorePct" else values.get(indicator)
        if isinstance(value, dict):
            # Daily VPOC distance is a fraction; model feature uses percentage points.
            value = value.get("VPOC_Distance")
            value = float(value) * 100 if value is not None else None
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = float("nan")
        row[name] = value if isfinite(value) else float("nan")
    return row
