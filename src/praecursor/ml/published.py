"""Learning examples from features and levels saved before the target session."""
from contextlib import closing
from datetime import date, datetime, time, timezone
import json
from pathlib import Path
import sqlite3
import pandas as pd
from praecursor.analysis.outcomes import LABEL_VERSION
from praecursor.core.sessions import CAIRO, next_session
from praecursor.ml.features import FEATURES, FEATURE_VERSION, feature_row


def published_samples(database):
    with closing(sqlite3.connect(Path(database).resolve().as_uri()+"?mode=ro", uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""SELECT s.*, v.next_day_hit, v.next_day_net_return,
            v.next_day_status, v.resolved_session, v.swing_hit, v.swing_net_return,
            v.swing_status, v.swing_resolved_session
            FROM scanner_signals s LEFT JOIN verified_outcomes v
            ON s.run_id=v.run_id AND s.symbol=v.symbol
            WHERE s.feature_version=? AND (v.label_version=? OR v.run_id IS NULL)
            ORDER BY s.generated_at,s.run_id""", (FEATURE_VERSION, LABEL_VERSION)).fetchall()
    records, seen = [], set()
    for row in rows:
        r = dict(row)
        session = r["feature_session"]
        if not session or not r["indicator_values_json"]:
            continue
        stamp = datetime.fromisoformat(r["generated_at"].replace("Z", "+00:00"))
        stamp = stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp
        # Conservative pre-market cutoff also admits early manual runs, never intraday hindsight.
        deadline = datetime.combine(next_session(date.fromisoformat(session)), time(9), CAIRO)
        if stamp.astimezone(CAIRO) >= deadline:
            continue
        key = (session, r["symbol"])
        if key in seen:
            continue
        seen.add(key)  # Never replace the first published features with a later rerun.
        values = json.loads(r["indicator_values_json"])
        features = feature_row(values, r["opportunity_score"])
        if (r["data_quality_score"] < 80 or r["latest_close"] < .2
                or not features["avg_turnover_20"] >= 250_000
                or sum(pd.isna(v) for v in features.values()) / len(FEATURES) > .2):
            continue
        record = dict(symbol=r["symbol"], session=session, opportunity_score=r["opportunity_score"],
                      candidate_rank=r["candidate_rank"], feature_version=FEATURE_VERSION,
                      label_version=LABEL_VERSION, provenance="published_prediction", **features)
        for h, maturity in (("next_day", "resolved_session"), ("swing", "swing_resolved_session")):
            record.update({h+"_target_hit": r[h+"_hit"], h+"_resolved_session": r[maturity],
                           h+"_net_return_pct": r[h+"_net_return"], h+"_status": r[h+"_status"] or "pending"})
        records.append(record)
    columns = ["symbol", "session", "opportunity_score", "candidate_rank", "feature_version",
               "label_version", "provenance", *FEATURES]
    columns += [h+suffix for h in ("next_day", "swing") for suffix in
                ("_target_hit", "_resolved_session", "_net_return_pct", "_status")]
    return pd.DataFrame(records, columns=columns)


def feedback_summary(frame):
    picks = frame[frame.candidate_rank.notna()]
    return dict(examples=len(frame), sessions=int(frame.session.nunique()), candidates=len(picks),
        hits=int(picks.next_day_target_hit.eq(1).sum()), misses=int(picks.next_day_target_hit.eq(0).sum()),
        unresolved=int(picks.next_day_target_hit.isna().sum()),
        provenance="Original published features; first prediction per symbol/session; incompatible legacy features excluded")
