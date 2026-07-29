from dataclasses import dataclass
from math import isnan

from praecursor.scoring.opportunity_score import OpportunityScore


@dataclass(frozen=True)
class SwingPrediction:
    """10-20 bar swing opportunity assessment."""

    score: float
    label: str
    reasons: list[str]

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
    trend_score, trend_reasons = _trend_continuation_score(values)
    reversal_score, reversal_reasons = _swing_reversal_score(values)
    quality_adjustment, quality_reasons = _quality_adjustment(
        consensus_accepted,
        consensus_confidence,
        data_quality_score,
    )

    raw_score = max(trend_score, reversal_score) + quality_adjustment
    score = max(0.0, min(raw_score, 100.0))
    label = _label(score, trend_score, reversal_score, consensus_accepted)

    if label in {"Swing Reversal Watch", "Swing Recovery Watch"}:
        reasons = reversal_reasons + quality_reasons
    else:
        reasons = trend_reasons + quality_reasons

    if not reasons:
        reasons.append("no strong swing pattern detected")

    return SwingPrediction(score=score, label=label, reasons=reasons)


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


def _label(score: float, trend_score: float, reversal_score: float, consensus_accepted: bool) -> str:
    if not consensus_accepted:
        return "Low Confidence"

    if reversal_score >= 70 and reversal_score >= trend_score:
        return "Swing Reversal Watch"

    if trend_score >= 70 and trend_score >= reversal_score:
        return "Swing Trend Continuation"

    if reversal_score >= 55 and reversal_score >= trend_score:
        return "Swing Recovery Watch"

    if score >= 60:
        return "Swing Watchlist"

    return "Avoid Swing"


def _missing(value: float) -> bool:
    return isnan(value)
