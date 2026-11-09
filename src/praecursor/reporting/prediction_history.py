"""Display saved next-session predictions and their verified, price-basis-matched results."""
from datetime import date
import re
from praecursor.core.sessions import next_session


def prediction_history(conn):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "scanner_signals" not in tables:
        return []
    columns = {r[1] for r in conn.execute("PRAGMA table_info(scanner_signals)")}
    feature = "s.feature_session" if "feature_session" in columns else "NULL"
    candidate = "s.candidate_rank" if "candidate_rank" in columns else "NULL"
    label = "s.next_day_label" if "next_day_label" in columns else "''"
    verified = "verified_outcomes" in tables
    fields = ("signal_date", "resolved_session", "next_day_hit", "next_day_return",
              "next_day_max_return", "next_day_status")
    outcomes = ",".join(f"v.{f}" if verified else f"NULL AS {f}" for f in fields)
    join = "LEFT JOIN verified_outcomes v ON v.run_id=s.run_id AND v.symbol=s.symbol" if verified else ""
    rows = conn.execute(f"""SELECT s.run_id,s.symbol,s.company,s.generated_at,s.latest_close,
        s.next_day_target,{feature} AS feature_session,{candidate} AS candidate_rank,{label} AS candidate_label,{outcomes}
        FROM scanner_signals s {join} ORDER BY s.generated_at,s.run_id,s.id""").fetchall()
    history, selected_runs, seen = [], {}, set()
    for row in rows:
        r = dict(row)
        rank = r["candidate_rank"]
        if rank is None:
            match = re.search(r"(?:Top Pick|Daily Candidate) #([1-5])\b", r["candidate_label"] or "")
            rank = int(match.group(1)) if match else None
        if rank not in (1, 2, 3, 4, 5):
            continue
        reference_session = r["feature_session"] or r["signal_date"]
        if not reference_session:
            continue
        target_session = r["resolved_session"] or next_session(date.fromisoformat(reference_session)).isoformat()
        selected_runs.setdefault(target_session, r["run_id"])
        if selected_runs[target_session] != r["run_id"] or (target_session, rank) in seen:
            continue
        seen.add((target_session, rank))
        hit = r["next_day_hit"]
        status = "hit" if hit == 1 else "miss" if hit == 0 else (
            "pending" if r["next_day_status"] in (None, "pending") else "unverified")
        reference = r["latest_close"]
        def actual(change):
            return reference * (1 + change / 100) if reference and change is not None else None
        history.append(dict(symbol=r["symbol"], company=r["company"],
            session=target_session, session_confirmed=r["resolved_session"] is not None,
            published_at=r["generated_at"], candidate_rank=rank,
            reference=reference, target=r["next_day_target"],
            actual_high=actual(r["next_day_max_return"]), actual_close=actual(r["next_day_return"]),
            close_change_pct=r["next_day_return"], status=status,
            outcome_status=r["next_day_status"] or "pending"))
    history.sort(key=lambda r: r["candidate_rank"])
    return sorted(history, key=lambda r: r["session"], reverse=True)
