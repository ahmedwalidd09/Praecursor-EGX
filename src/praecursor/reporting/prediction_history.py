"""Display saved next-session predictions and their verified, price-basis-matched results."""
from praecursor.analysis.outcomes import outcome_category
from praecursor.analysis.published_history import original_predictions


def prediction_history(conn):
    history = []
    for r in original_predictions(conn):
        rank = r["candidate_rank"]
        if rank not in range(1, 6):
            continue
        hit = r["next_day_hit"]
        status = "hit" if hit == 1 else "miss" if hit == 0 else (
            "pending" if r["next_day_status"] in (None, "pending") else "unverified")
        reference = r["latest_close"]
        def actual(change):
            return reference * (1 + change / 100) if reference and change is not None else None
        history.append(dict(symbol=r["symbol"], company=r["company"],
            session=r["target_session"], session_confirmed=r["resolved_session"] is not None,
            published_at=r["generated_at"], candidate_rank=rank,
            reference=reference, target=r["next_day_target"],
            actual_high=actual(r["next_day_max_return"]), actual_close=actual(r["next_day_return"]),
            close_change_pct=r["next_day_return"], status=status,
            trade_category=outcome_category(r["next_day_status"],r["next_day_net_return"]),
            net_return_pct=r["next_day_net_return"],
            outcome_status=r["next_day_status"] or "pending"))
    history.sort(key=lambda r: r["candidate_rank"])
    return sorted(history, key=lambda r: r["session"], reverse=True)
