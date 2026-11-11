"""Original pre-open runs and horizon-aligned evidence for dated predictions."""
from datetime import date, datetime, time, timezone
from functools import cache
import re
import sqlite3

from praecursor.analysis.outcomes import LABEL_VERSION
from praecursor.core.sessions import CAIRO, session_horizon


def original_predictions(conn):
    """Yield rows from the first saved pre-open run for each target session."""
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "scanner_signals" not in tables:
        return
    outcome_columns = {r[1] for r in conn.execute("PRAGMA table_info(verified_outcomes)")}
    fields = ("signal_date", "label_version", "resolved_session", "next_day_hit", "next_day_trade_hit",
              "next_day_return", "next_day_max_return", "next_day_net_return", "next_day_status",
              "swing_resolved_session", "swing_hit", "swing_net_return", "swing_status")
    outcomes = ",".join(f"v.{f}" if f in outcome_columns else f"NULL AS {f}" for f in fields)
    join = "LEFT JOIN verified_outcomes v ON v.run_id=s.run_id AND v.symbol=s.symbol" if outcome_columns else ""
    rows = conn.cursor()
    rows.row_factory = sqlite3.Row
    rows.execute(f"""SELECT s.*,{outcomes} FROM scanner_signals s {join}
        ORDER BY julianday(s.generated_at),s.run_id,s.symbol""")
    first_runs, seen = {}, set()
    horizon_dates = cache(session_horizon)
    for row in rows:
        r = dict(row)
        rank = r.get("candidate_rank")
        if rank is None:
            match = re.search(r"(?:Top Pick|Daily Candidate) #([1-5])\b", r.get("next_day_label") or "")
            rank = int(match.group(1)) if match else None
        ref = r.get("feature_session") or r["signal_date"]
        if not ref or (not r.get("feature_session") and rank not in range(1, 6)):
            continue
        dates = horizon_dates(ref, 20)
        target = dates[0]
        stamp = datetime.fromisoformat(r["generated_at"].replace("Z", "+00:00"))
        stamp = stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp
        if stamp >= datetime.combine(date.fromisoformat(target), time(9), CAIRO):
            continue
        first_runs.setdefault(target, r["run_id"])
        key = (target, r["symbol"])
        if first_runs[target] != r["run_id"] or key in seen:
            continue
        seen.add(key)

        # Keep stored evidence intact. A shifted or incompatible label cannot
        # contribute to current measurement or model promotion.
        for horizon, maturity, expected, values in (
            ("next_day", "resolved_session", target,
             ("next_day_hit", "next_day_trade_hit", "next_day_return", "next_day_max_return", "next_day_net_return")),
            ("swing", "swing_resolved_session", dates[-1], ("swing_hit", "swing_net_return")),
        ):
            if r[maturity] == expected and r["label_version"] == LABEL_VERSION:
                continue
            if not r[maturity] and all(r[field] is None for field in values):
                continue
            if not r[maturity]:
                reason = "unverified_outcome"
            elif r[maturity] != expected:
                reason = "misaligned_session"
            else:
                reason = "incompatible_outcome"
            r[horizon + "_status"] = reason
            for field in (*values, maturity):
                r[field] = None
        r.update(candidate_rank=rank, target_session=target)
        yield r
