"""Versioned target-touch and next-open execution labels, shared by training and tracking."""
from dataclasses import dataclass
from math import isfinite

LABEL_VERSION = "3"


@dataclass(frozen=True)
class Outcome:
    status: str
    target_hit: int | None = None
    trade_hit: int | None = None
    net_return_pct: float | None = None
    close_return_pct: float | None = None
    max_return_pct: float | None = None
    resolved_session: str | None = None


def evaluate_path(candles, reference, target, stop, horizon, cost_bps=25.0):
    """Enter at next open; ambiguous same-bar barriers remain unlabelled for trade success.

    cost_bps is an explicit round-trip fee/slippage scenario, not a claim about broker charges.
    Missing sessions must be represented by None, never silently skipped.
    """
    if not all(isfinite(x) and x > 0 for x in (reference, target)) or not reference < target:
        return Outcome("invalid_levels")
    if len(candles) < horizon:
        return Outcome("pending")
    bars = candles[:horizon]
    if any(b is None for b in bars):
        return Outcome("missing_or_conflicting_candle")
    previous = reference
    for bar in bars:
        if abs(bar.open / previous - 1) > .25:
            return Outcome("corporate_action_review")
        previous = bar.close
    hit = int(any(b.high >= target for b in bars))
    common = dict(target_hit=hit, close_return_pct=(bars[-1].close / reference - 1) * 100,
                  max_return_pct=(max(b.high for b in bars) / reference - 1) * 100,
                  resolved_session=bars[-1].session)
    if not isfinite(stop) or not 0 < stop < reference:
        return Outcome("no_recorded_stop", **common)
    entry = bars[0].open
    if entry >= target or entry <= stop or bars[0].low == bars[0].high:
        return Outcome("unfilled", net_return_pct=0.0, **common)
    exit_price = bars[-1].close
    status = "horizon_exit"
    for bar in bars:
        if bar.open <= stop:
            exit_price, status = bar.open, "stop"
            break
        if bar.open >= target:
            exit_price, status = target, "target"
            break
        if bar.low <= stop and bar.high >= target:
            # Return is a conservative scenario; trade success remains unknown.
            return Outcome("ambiguous_barrier_order", net_return_pct=(stop/entry-1)*100-cost_bps/100, **common)
        if bar.low <= stop:
            exit_price, status = stop, "stop"
            break
        if bar.high >= target:
            exit_price, status = target, "target"
            break
    net = (exit_price / entry - 1) * 100 - cost_bps / 100
    return Outcome(status, trade_hit=int(net > 0), net_return_pct=net, **common)
