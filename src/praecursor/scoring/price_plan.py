"""Versions and assumptions for published reference levels."""
from math import isfinite

from praecursor.analysis.outcomes import SCENARIO_COST_BPS

NEXT_DAY_POLICY = "structure-atr-v2"
SWING_POLICY = "swing-atr-v2"


def valid_price(value):
    return value is not None and isfinite(value) and value > 0


def price_text(value):
    if not valid_price(value):
        return "Unavailable"
    return f"{value:.10g}"


def plan_evidence(policy, horizon, close, target, stop, atr, target_reason, stop_reason):
    valid = all(valid_price(value) for value in (close, target, stop)) and stop < close < target
    result = dict(policy=policy, horizon_sessions=horizon, atr14=atr if valid_price(atr) else None,
                  status="heuristic-active" if valid else "unavailable",
                  target_reason=target_reason, stop_reason=stop_reason)
    if valid:
        reward, risk = target - close, close - stop
        cost = close * SCENARIO_COST_BPS / 10_000
        result.update(gross_reward_risk=reward / risk, net_reward_risk=(reward - cost) / (risk + cost),
                      scenario_cost_bps=SCENARIO_COST_BPS)
    return result
