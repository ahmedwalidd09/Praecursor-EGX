"""Read-only dashboard view of saved signals and versioned validation evidence."""
from pathlib import Path
from contextlib import closing
import json
import math
import sqlite3
from praecursor.storage.database import DATABASE
from praecursor.ml.features import FEATURE_VERSION
from praecursor.core.sessions import completed_session, next_session
from datetime import date

ROOT=Path(__file__).resolve().parents[3]


def clean(value):
    """Represent unavailable numeric measurements as JSON null."""
    if isinstance(value,float) and not math.isfinite(value): return None
    if isinstance(value,dict): return {k:clean(v) for k,v in value.items()}
    if isinstance(value,list): return [clean(v) for v in value]
    return value


def overview(database=DATABASE):
    result=dict(signals=[],scan=None,price_session=None,expected_session=completed_session().isoformat(),
                outcomes={},validation={},model_status="Technical scoring",stale=True)
    for horizon in ("next_day","swing"):
        path=ROOT/"reports"/f"{horizon}_validation.json"
        if path.exists():
            result["validation"][horizon]=json.loads(path.read_text(encoding="utf-8"))
    if not Path(database).exists():
        return clean(result)
    with closing(sqlite3.connect(Path(database).resolve().as_uri()+"?mode=ro",uri=True)) as conn:
        conn.row_factory=sqlite3.Row
        tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "source_prices" in tables:
            result["price_session"]=conn.execute("SELECT max(date(trade_date)) FROM source_prices WHERE source!='mubasher'").fetchone()[0]
        if "scanner_runs" in tables:
            run=conn.execute("SELECT * FROM scanner_runs WHERE id IN (SELECT run_id FROM scanner_signals) ORDER BY id DESC LIMIT 1").fetchone()
            if run:
                result["scan"]=dict(run)
                signals=conn.execute("SELECT * FROM scanner_signals WHERE run_id=? ORDER BY next_day_score DESC,symbol",(run["id"],)).fetchall()
                for r in signals:
                    row=dict(r)
                    row["selection_reasons"]=json.loads(row.get("selection_reasons") or "[]")
                    row["legacy"]=row.get("feature_version")!=FEATURE_VERSION
                    row["next_day_probability"]=None if row["legacy"] else row.get("next_day_probability")
                    result["signals"].append(row)
                result["stale"]=any(r["legacy"] or r.get("feature_session")!=result["expected_session"] for r in result["signals"])
        if "verified_outcomes" in tables:
            # Count one published prediction per symbol/session, keeping the earliest.
            rows=conn.execute("""WITH ranked AS (
              SELECT *,ROW_NUMBER() OVER(PARTITION BY signal_date,symbol ORDER BY run_id) AS n
              FROM verified_outcomes)
              SELECT * FROM ranked WHERE n=1""").fetchall()
            known=[r for r in rows if r["next_day_hit"] is not None]
            traded=[r for r in rows if r["next_day_trade_hit"] is not None]
            result["outcomes"]=dict(total=len(known),hits=sum(r["next_day_hit"] for r in known),
                target_hit_rate=sum(r["next_day_hit"] for r in known)/len(known) if known else None,
                executable_trades=len(traded),trade_win_rate=sum(r["next_day_trade_hit"] for r in traded)/len(traded) if traded else None,
                uncertain=sum(r["next_day_status"] in ("ambiguous_barrier_order","missing_or_conflicting_candle","corporate_action_review","no_recorded_stop") for r in rows))
    if result["signals"]:
        feature_session=result["signals"][0].get("feature_session")
        result["target_session"]=next_session(date.fromisoformat(feature_session)).isoformat() if feature_session else None
    # SQLite and report JSON may contain NaN from unavailable measurements.
    return clean(result)
