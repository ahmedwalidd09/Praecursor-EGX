from dataclasses import dataclass
from math import isnan

from praecursor.scoring.opportunity_score import OpportunityScore


@dataclass(frozen=True)
class NextDayPrediction:
    """Next-session breakout/follow-through assessment."""

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
    label = _label(score, rsi14, breakout20, breakout50, volume_confirmed_breakout, consensus_accepted)

    if not reasons:
        reasons.append("no strong next-day breakout/follow-through pattern detected")

    return NextDayPrediction(score=score, label=label, reasons=reasons)


def _label(
    score: float,
    rsi14: float,
    breakout20: float,
    breakout50: float,
    volume_confirmed_breakout: float,
    consensus_accepted: bool,
) -> str:
    if not consensus_accepted:
        return "Low Confidence"

    is_breakout = breakout20 == 1.0 and breakout50 == 1.0
    is_volume_confirmed = volume_confirmed_breakout == 1.0
    is_overextended = not _missing(rsi14) and rsi14 > 75

    if score >= 75 and is_breakout and is_volume_confirmed:
        if is_overextended:
            return "Next-Day Breakout Candidate - Extended"
        return "Next-Day Breakout Candidate"

    if score >= 65:
        return "High-Priority Next-Day Watch"

    if score >= 50:
        return "Watchlist Tomorrow"

    return "Avoid Tomorrow"


def _missing(value: float) -> bool:
    return isnan(value)
