from dataclasses import dataclass
from math import isnan

from praecursor.scoring.opportunity_score import OpportunityScore


@dataclass(frozen=True)
class NextDayPrediction:
    """Next-session readiness assessment."""

    score: float
    label: str
    reasons: list[str]

    @property
    def reasons_text(self) -> str:
        return "; ".join(self.reasons)


def calculate_next_day_prediction(
    opportunity_score: OpportunityScore,
    consensus_accepted: bool = True,
    consensus_confidence: float = 40.0,
    data_quality_score: float = 100.0,
) -> NextDayPrediction:
    """Calculate next-session prediction using breakout and early-reversal lenses."""
    values = opportunity_score.indicator_values
    breakout_score, breakout_reasons = _breakout_score(values)
    reversal_score, reversal_reasons = _reversal_score(values)
    quality_adjustment, quality_reasons = _quality_adjustment(
        values,
        consensus_accepted,
        consensus_confidence,
        data_quality_score,
    )

    raw_score = max(breakout_score, reversal_score) + quality_adjustment
    score = max(0.0, min(raw_score, 100.0))
    label = _label(score, breakout_score, reversal_score, values, consensus_accepted)
    reasons = _reasons_for_label(label, breakout_reasons, reversal_reasons, quality_reasons)

    if not reasons:
        reasons.append("no strong next-day catalyst pattern detected")

    return NextDayPrediction(score=score, label=label, reasons=reasons)


def _breakout_score(values: dict[str, float]) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 0.0

    trend_strength = values.get("TrendStrength", float("nan"))
    breakout20 = values.get("Breakout20", float("nan"))
    breakout50 = values.get("Breakout50", float("nan"))
    volume_confirmed_breakout = values.get("VolumeConfirmedBreakout", float("nan"))
    near_high = values.get("NearCloseHigh250Percent", float("nan"))
    macd = values.get("MACD", float("nan"))
    macd_histogram = values.get("MACDHistogram", float("nan"))
    momentum20 = values.get("Momentum20", float("nan"))
    relative_volume20 = values.get("RelVolume20", float("nan"))

    if not _missing(trend_strength):
        score += min(max(trend_strength, 0.0), 100.0) * 0.15
        if trend_strength >= 75:
            reasons.append("trend structure is strong")

    if breakout20 == 1.0:
        score += 14.0
        reasons.append("20-bar closing breakout is active")
    if breakout50 == 1.0:
        score += 10.0
        reasons.append("50-bar closing breakout is active")
    if volume_confirmed_breakout == 1.0:
        score += 14.0
        reasons.append("breakout is volume-confirmed")
    if not _missing(near_high):
        if near_high >= -3.0:
            score += 5.0
            reasons.append("close is within 3% of 250-bar closing high")
        elif near_high >= -7.0:
            score += 2.0
            reasons.append("close is near its 250-bar closing high")

    if not _missing(macd) and macd > 0:
        score += 5.0
    if not _missing(macd_histogram) and macd_histogram > 0:
        score += 7.0
        reasons.append("MACD acceleration is positive")
    if not _missing(momentum20):
        if momentum20 >= 10.0:
            score += 8.0
            reasons.append("20-bar momentum is strong")
        elif momentum20 >= 3.0:
            score += 5.0
            reasons.append("20-bar momentum is positive")
        elif momentum20 > 0:
            score += 2.0

    if not _missing(relative_volume20):
        if relative_volume20 >= 1.5:
            score += 18.0
            reasons.append("relative volume is strongly elevated")
        elif relative_volume20 >= 1.0:
            score += 10.0
            reasons.append("relative volume supports the move")
        elif relative_volume20 >= 0.75:
            score += 5.0
            reasons.append("relative volume is acceptable but not strong")
        else:
            reasons.append("relative volume is weak")

    return min(score, 100.0), reasons


def _reversal_score(values: dict[str, float]) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 0.0

    rsi14 = values.get("RSI14", float("nan"))
    rsi_rebound = values.get("RSIRebound", float("nan"))
    ema20_reclaim = values.get("EMA20Reclaim", float("nan"))
    macd_histogram = values.get("MACDHistogram", float("nan"))
    macd_improvement = values.get("MACDHistogramImprovement", float("nan"))
    volume_spike = values.get("VolumeSpikeFromWeakness", float("nan"))
    momentum5 = values.get("Momentum5", float("nan"))
    momentum20 = values.get("Momentum20", float("nan"))
    relative_volume20 = values.get("RelVolume20", float("nan"))

    weak_or_oversold = not _missing(rsi14) and rsi14 <= 50
    prior_weakness = not _missing(momentum20) and momentum20 <= 3

    if weak_or_oversold:
        score += 12.0
        reasons.append("RSI is in a weak/oversold recovery zone")

    if rsi_rebound == 1.0:
        score += 18.0
        reasons.append("RSI is rebounding from weakness")

    if ema20_reclaim == 1.0:
        score += 18.0
        reasons.append("price reclaimed EMA20")

    if not _missing(macd_improvement) and macd_improvement > 0:
        score += 12.0
        reasons.append("MACD histogram is improving")

    if not _missing(macd_histogram) and macd_histogram > 0:
        score += 8.0
        reasons.append("MACD histogram is positive")

    if volume_spike == 1.0:
        score += 18.0
        reasons.append("volume spiked after weakness")
    elif not _missing(relative_volume20) and relative_volume20 >= 1.25 and prior_weakness:
        score += 12.0
        reasons.append("relative volume expanded after weak momentum")

    if not _missing(momentum5):
        if momentum5 >= 5:
            score += 14.0
            reasons.append("5-bar reversal momentum is strong")
        elif momentum5 > 0:
            score += 8.0
            reasons.append("5-bar reversal momentum is positive")

    if not prior_weakness and not weak_or_oversold:
        score *= 0.55
        if score > 0:
            reasons.append("reversal score discounted because prior weakness is limited")

    return min(score, 100.0), reasons


def _quality_adjustment(
    values: dict[str, float],
    consensus_accepted: bool,
    consensus_confidence: float,
    data_quality_score: float,
) -> tuple[float, list[str]]:
    reasons: list[str] = []
    adjustment = 0.0
    rsi14 = values.get("RSI14", float("nan"))

    if consensus_accepted:
        adjustment += min(consensus_confidence, 100.0) * 0.05
    else:
        adjustment -= 20.0
        reasons.append("latest close consensus is not accepted")

    if data_quality_score < 60:
        adjustment -= 10.0
        reasons.append("data quality is low")

    if not _missing(rsi14):
        if rsi14 > 80:
            adjustment -= 15.0
            reasons.append("RSI is extremely overextended")
        elif rsi14 > 75:
            adjustment -= 8.0
            reasons.append("RSI is overextended")

    return adjustment, reasons


def _label(
    score: float,
    breakout_score: float,
    reversal_score: float,
    values: dict[str, float],
    consensus_accepted: bool,
) -> str:
    if not consensus_accepted:
        return "Low Confidence"

    rsi14 = values.get("RSI14", float("nan"))
    breakout20 = values.get("Breakout20", float("nan"))
    breakout50 = values.get("Breakout50", float("nan"))
    volume_confirmed_breakout = values.get("VolumeConfirmedBreakout", float("nan"))
    is_breakout = breakout20 == 1.0 and breakout50 == 1.0
    is_volume_confirmed = volume_confirmed_breakout == 1.0
    is_overextended = not _missing(rsi14) and rsi14 > 75

    if reversal_score >= 70 and reversal_score >= breakout_score:
        return "Early Reversal Watch"

    if score >= 75 and is_breakout and is_volume_confirmed:
        if is_overextended:
            return "Next-Day Explosion Candidate - Extended"
        return "Next-Day Explosion Candidate"

    if score >= 65:
        return "High-Priority Watch"

    if reversal_score >= 55 and reversal_score >= breakout_score:
        return "Reversal Watchlist"

    if score >= 50:
        return "Watchlist Tomorrow"

    return "Avoid Tomorrow"


def _reasons_for_label(
    label: str,
    breakout_reasons: list[str],
    reversal_reasons: list[str],
    quality_reasons: list[str],
) -> list[str]:
    if label in {"Early Reversal Watch", "Reversal Watchlist"}:
        return reversal_reasons + quality_reasons

    return breakout_reasons + quality_reasons


def _missing(value: float) -> bool:
    return isnan(value)
