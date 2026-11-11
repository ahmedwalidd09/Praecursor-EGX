"""Learning examples from features and levels saved before the target session."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import pandas as pd
from praecursor.analysis.outcomes import LABEL_VERSION
from praecursor.analysis.published_history import original_predictions
from praecursor.ml.features import FEATURES, FEATURE_VERSION, feature_row


def eligible_features(r):
    """Original price, liquidity and feature gates for the matched universe."""
    if (not r.get("feature_session") or r.get("feature_version") != FEATURE_VERSION
            or not r.get("indicator_values_json") or (r.get("data_quality_score") or 0) < 80
            or (r.get("latest_close") or 0) < .2):
        return None
    try:
        values = json.loads(r["indicator_values_json"])
    except ValueError:
        return None
    if not isinstance(values, dict):
        return None
    features = feature_row(values, r["opportunity_score"])
    if (not features["avg_turnover_20"] >= 250_000
            or sum(pd.isna(v) for v in features.values()) / len(FEATURES) > .2):
        return None
    return features


def published_samples(database):
    records = []
    with closing(sqlite3.connect(Path(database).resolve().as_uri()+"?mode=ro", uri=True)) as conn:
        for r in original_predictions(conn):
            features = eligible_features(r)
            if features is None:
                continue
            record = dict(symbol=r["symbol"], session=r["feature_session"], opportunity_score=r["opportunity_score"],
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
        provenance="Original published features; first published run per feature session; incompatible legacy features excluded")
