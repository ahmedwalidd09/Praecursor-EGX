"""Daily research shortlist, separate from price-source confidence and model probability."""
from collections import Counter
from dataclasses import replace
from math import isfinite

SHORTLIST_POLICY = "verified-egp-v1"
MIN_PRICE_EGP = .20
MIN_TURNOVER_EGP = 250_000


def technical_exclusion(quality, close, turnover, score, target, stop, source_status, limit_up):
    if any(v is None or not isfinite(float(v)) for v in (close, turnover, score, target, stop)):
        return "Missing price, turnover or plan levels"
    if quality < 80:
        return "Insufficient price history or quality"
    if close < MIN_PRICE_EGP:
        return "Reference close below EGP 0.20"
    if turnover < MIN_TURNOVER_EGP:
        return "Average turnover below EGP 250,000"
    if not 0 < stop < close < target:
        return "Invalid levels for the reference close"
    if source_status.startswith("Source disagreement"):
        return "Latest close disagrees across sources"
    if limit_up == 1:
        return "Closed at its upper price limit"
    return None


def select_daily_candidates(results, *, currencies, count=5):
    eligible, reviewed = [], []
    for item in results:
        currency = currencies[item.symbol]
        status = currency["status"]
        exclusion = None
        if status != "verified":
            exclusion = {
                "unknown": "Quote currency unverified",
                "stale": "Quote currency evidence expired",
                "conflicting": "Quote currency sources disagree",
            }[status]
        elif currency["currency"] != "EGP":
            exclusion = f"{currency['currency']} quote · outside the EGP shortlist"
        else:
            prediction = item.next_day_prediction
            score = item.opportunity_score
            values = score.indicator_values
            exclusion = technical_exclusion(item.data_quality_score, score.latest_close,
                values.get("AvgTurnover20"), prediction.score, prediction.target_price,
                prediction.stop_loss_price, item.source_status, values.get("ClosedAtLimitUp"))
        item = replace(item, shortlist=dict(currency, policy=SHORTLIST_POLICY, exclusion=exclusion))
        reviewed.append(item)
        if exclusion is None:
            eligible.append(item)

    eligible.sort(key=lambda r: (-r.next_day_score, r.symbol))
    chosen, sectors = [], Counter()
    # Prefer a spread of sectors; fill remaining slots if the eligible universe is narrow.
    for item in eligible:
        sector = getattr(item.opportunity_score.stock, "sector", "")
        if sector and sector != "General" and sectors[sector] >= 2:
            continue
        chosen.append(item)
        sectors[sector] += 1
        if len(chosen) == count:
            break
    chosen_symbols = {item.symbol for item in chosen}
    chosen.extend(item for item in eligible if item.symbol not in chosen_symbols)
    replacements = {}
    for rank, item in enumerate(chosen[:count], 1):
        p = item.next_day_prediction
        score = item.opportunity_score
        v = score.indicator_values
        rr = (p.target_price - score.latest_close) / (score.latest_close - p.stop_loss_price)
        reasons = [f"Setup score {p.score:.1f}/100; among the strongest eligible setups today",
                   f"Reference reward/risk {rr:.2f}x; average turnover EGP {v['AvgTurnover20']:,.0f}"]
        if v.get("Breakout20") == 1:
            reasons.append("Close broke the previous 20-session high")
        elif v.get("EMA20", float("inf")) < score.latest_close:
            reasons.append("Close is above its 20-session EMA")
        elif v.get("RelVolume20", 0) >= 1:
            reasons.append(f"Volume is {v['RelVolume20']:.2f}x its 20-session average")
        else:
            reasons.append("Relative shortlist selection; no strong trend confirmation")
        replacements[item.symbol] = replace(item, candidate_rank=rank,
            selection_reasons=tuple(reasons), override_next_day_label=f"Daily Candidate #{rank}")
    return [replacements.get(item.symbol, item) for item in reviewed]
