"""Daily research shortlist, separate from price-source confidence and model probability."""
from collections import Counter
from dataclasses import replace
from math import isfinite


def select_daily_candidates(results, count=5):
    eligible = []
    for item in results:
        prediction = item.next_day_prediction
        score = item.opportunity_score
        values = score.indicator_values
        turnover = values.get("AvgTurnover20", 0)
        numbers = (prediction.score, score.latest_close, prediction.target_price, prediction.stop_loss_price, turnover)
        if any(v is None or not isfinite(float(v)) for v in numbers):
            continue
        if item.data_quality_score < 80 or score.latest_close < .2 or turnover < 250_000:
            continue
        if not 0 < prediction.stop_loss_price < score.latest_close < prediction.target_price:
            continue
        if item.consensus_result is not None and not item.consensus_result.accepted:
            continue
        if values.get("ClosedAtLimitUp") == 1:
            continue
        eligible.append(item)
    eligible.sort(key=lambda r: (-r.next_day_score, r.symbol))
    chosen, sectors = [], Counter()
    # Prefer a spread of sectors; fill remaining slots if the eligible universe is narrow.
    for item in eligible:
        sector = getattr(item.opportunity_score.stock, "sector", "")
        if sector and sector != "General" and sectors[sector] >= 2:
            continue
        chosen.append(item); sectors[sector] += 1
        if len(chosen) == count: break
    chosen_symbols = {item.symbol for item in chosen}
    chosen.extend(item for item in eligible if item.symbol not in chosen_symbols)
    replacements = {}
    for rank, item in enumerate(chosen[:count], 1):
        p = item.next_day_prediction
        score = item.opportunity_score
        v = score.indicator_values
        rr = (p.target_price-score.latest_close)/(score.latest_close-p.stop_loss_price)
        reasons = [f"Setup score {p.score:.1f}/100; among the strongest eligible setups today",
                   f"Target/stop reward-to-risk {rr:.2f}x; average turnover {v['AvgTurnover20']:,.0f} quote units"]
        if v.get("Breakout20") == 1:
            reasons.append("Close broke the previous 20-session high")
        elif v.get("EMA20", float('inf')) < score.latest_close:
            reasons.append("Close is above its 20-session EMA")
        elif v.get("RelVolume20", 0) >= 1:
            reasons.append(f"Volume is {v['RelVolume20']:.2f}x its 20-session average")
        else:
            reasons.append("Relative shortlist selection; no strong trend confirmation")
        replacements[item.symbol] = replace(item, candidate_rank=rank,
            selection_reasons=tuple(reasons), override_next_day_label=f"Daily Candidate #{rank}")
    return [replacements.get(item.symbol, item) for item in results]
