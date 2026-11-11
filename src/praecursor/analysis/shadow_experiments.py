"""Sequential predeclared filter trials; only unseen completed sessions can qualify."""
from datetime import date, datetime, time, timezone
import json

from praecursor.core.sessions import CAIRO, completed_session, next_session
from praecursor.ml.rolling import block_mean_interval

TRIALS = [
    dict(name="liquidity_1m_v1", minimum_turnover=1_000_000,
         description="Keep original top-five names with 20-session turnover >= EGP 1m"),
    dict(name="positive_breadth_v1", minimum_breadth=.6,
         description="Hold cash unless >=60% of published universe has positive 20-session momentum"),
]
SCHEMA = """
CREATE TABLE IF NOT EXISTS shadow_experiments (
 name TEXT PRIMARY KEY, definition TEXT, registered_at TEXT, status TEXT, decision_at TEXT, result TEXT);
CREATE TABLE IF NOT EXISTS shadow_sessions (
 name TEXT, session TEXT, run_id INTEGER, choices TEXT, result TEXT,
 PRIMARY KEY(name,session));
"""


def choose(rows, definition):
    values = {r["symbol"]:json.loads(r["indicator_values_json"] or "{}") for r in rows}
    picks = [r["symbol"] for r in rows if r["candidate_rank"] in (1,2,3,4,5)]
    if "minimum_turnover" in definition:
        currencies = {r["symbol"]:r.get("quote_currency") for r in rows}
        return [s for s in picks if currencies[s] == "EGP" and (values[s].get("AvgTurnover20") or 0) >= definition["minimum_turnover"]]
    momenta = [v.get("Momentum20") for v in values.values() if isinstance(v.get("Momentum20"), (float,int))]
    return picks if len(momenta) >= 10 and sum(m>0 for m in momenta)/len(momenta) >= definition["minimum_breadth"] else []


def record_shadow(conn, run_id, now=None):
    conn.executescript(SCHEMA)
    now = now or datetime.now(timezone.utc)
    rows = [dict(r) for r in conn.execute("SELECT * FROM scanner_signals WHERE run_id=?", (run_id,))]
    from praecursor.analysis.data_quality import currency_evidence
    for row in rows:
        row["quote_currency"] = currency_evidence(conn, row["symbol"], now)
    picks = [r for r in rows if r["candidate_rank"] in (1,2,3,4,5)]
    if len(picks) != 5 or not picks[0].get("feature_session"):
        return
    feature = picks[0]["feature_session"]
    session = next_session(date.fromisoformat(feature))
    if feature != completed_session(now).isoformat() or now >= datetime.combine(session,time(9),CAIRO):
        return
    # A rerun cannot replace the original shortlist or seed a new trial on hindsight.
    first = conn.execute("SELECT min(run_id) FROM scanner_signals WHERE feature_session=? AND candidate_rank BETWEEN 1 AND 5", (feature,)).fetchone()[0]
    if first != run_id:
        return
    existing = {r["name"]:dict(r) for r in conn.execute("SELECT * FROM shadow_experiments")}
    for definition in TRIALS:
        name = definition["name"]
        if name not in existing:
            conn.execute("INSERT INTO shadow_experiments VALUES (?,?,?,'collecting',NULL,NULL)",
                         (name,json.dumps(definition,sort_keys=True),now.isoformat()))
        elif existing[name]["status"] != "collecting":
            continue
        else:
            definition = json.loads(existing[name]["definition"])
        choices = dict(baseline=[r["symbol"] for r in picks], selected=choose(rows,definition))
        conn.execute("INSERT OR IGNORE INTO shadow_sessions VALUES (?,?,?,?,NULL)",
                     (name,session.isoformat(),run_id,json.dumps(choices)))
        break  # One trial at a time, never a grid search over this evidence.
    conn.commit()


def trial_decision(daily):
    if len(daily) < 60 or any(d is None for d in daily[:60]):
        return None
    daily = daily[:60]
    deltas = [d["excess_pct"] for d in daily]
    interval = block_mean_interval(deltas)
    winning_blocks = sum(sum(deltas[i:i+20])>0 for i in (0,20,40))
    stress = sum(d["stressed_return_pct"] for d in daily)/60
    approved = interval is not None and interval[0]>0 and winning_blocks>=2 and stress>0
    return dict(approved=approved, sessions=60, excess_95pct_interval=interval,
        winning_blocks=winning_blocks, stressed_return_pct=stress,
        status="Passed fixed unseen-session gate" if approved else "Rejected: insufficient consistent advantage",
        basis="Five equal slots; rejected names stay cash; 25 bps base costs plus 50 bps stress per fill")


def resolve_shadows(conn, now=None):
    conn.executescript(SCHEMA)
    now = now or datetime.now(timezone.utc)
    terminal = {"target", "stop", "horizon_exit", "unfilled", "ambiguous_barrier_order"}
    for trial in conn.execute("SELECT * FROM shadow_experiments WHERE status='collecting'").fetchall():
        for day in conn.execute("SELECT * FROM shadow_sessions WHERE name=? AND result IS NULL ORDER BY session", (trial["name"],)).fetchall():
            if day["session"] > completed_session(now).isoformat():
                continue
            choices = json.loads(day["choices"])
            outcomes = {r["symbol"]:dict(r) for r in conn.execute("SELECT * FROM verified_outcomes WHERE run_id=?", (day["run_id"],))}
            if any(s not in outcomes or outcomes[s]["next_day_status"] not in terminal or
                   outcomes[s]["next_day_net_return"] is None for s in choices["baseline"]):
                continue
            baseline = sum(outcomes[s]["next_day_net_return"] for s in choices["baseline"])/5
            selected = sum(outcomes[s]["next_day_net_return"] for s in choices["selected"])/5
            fills = sum(outcomes[s]["next_day_status"] != "unfilled" for s in choices["selected"])
            result = dict(baseline_return_pct=baseline, candidate_return_pct=selected,
                          excess_pct=selected-baseline, stressed_return_pct=selected-.5*fills/5)
            conn.execute("UPDATE shadow_sessions SET result=? WHERE name=? AND session=?",
                         (json.dumps(result),trial["name"],day["session"]))
        daily = [json.loads(r[0]) if r[0] else None for r in conn.execute("SELECT result FROM shadow_sessions WHERE name=? ORDER BY session LIMIT 60", (trial["name"],))]
        decision = trial_decision(daily)
        if decision:
            conn.execute("UPDATE shadow_experiments SET status=?,decision_at=?,result=? WHERE name=?",
                         ("approved" if decision["approved"] else "rejected", now.isoformat(),json.dumps(decision),trial["name"]))
    conn.commit()
    return [dict(name=r["name"],status=r["status"],definition=json.loads(r["definition"]),
                 result=json.loads(r["result"]) if r["result"] else None,
                 collected_sessions=conn.execute("SELECT count(*) FROM shadow_sessions WHERE name=?",(r["name"],)).fetchone()[0],
                 resolved_sessions=conn.execute("SELECT count(*) FROM shadow_sessions WHERE name=? AND result IS NOT NULL",(r["name"],)).fetchone()[0])
            for r in conn.execute("SELECT * FROM shadow_experiments ORDER BY registered_at")]


def approved_paper_filter(conn, run_id, now):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='shadow_experiments'").fetchone():
        return None
    trial = conn.execute("""SELECT * FROM shadow_experiments WHERE status='approved' AND
        datetime(decision_at)<datetime(?) ORDER BY datetime(decision_at) DESC LIMIT 1""", (now.isoformat(),)).fetchone()
    if not trial:
        return None
    rows = [dict(r) for r in conn.execute("SELECT * FROM scanner_signals WHERE run_id=?", (run_id,))]
    from praecursor.analysis.data_quality import currency_evidence
    for row in rows:
        row["quote_currency"] = currency_evidence(conn, row["symbol"], now)
    return dict(name=trial["name"], definition=json.loads(trial["definition"]),
                allowed=choose(rows,json.loads(trial["definition"])), decision_at=trial["decision_at"])
