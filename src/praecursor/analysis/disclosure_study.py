"""Prospective matched comparison of consolidated-results notices."""
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
import json
from math import isfinite
from statistics import mean

from praecursor.analysis.data_quality import currency_evidence
from praecursor.analysis.outcomes import LABEL_VERSION
from praecursor.core.sessions import CAIRO, completed_session, next_session
from praecursor.ml.published import eligible_features
from praecursor.ml.rolling import block_mean_interval

VERSION = "consolidated-results-1"
MIN_PAIRS = 60
SCHEMA = """CREATE TABLE IF NOT EXISTS disclosure_study_sessions (
    session TEXT PRIMARY KEY, run_id INTEGER NOT NULL, snapshot TEXT NOT NULL
);"""


def record_disclosure_study(conn, run_id, now=None):
    """Freeze an event and a same-session control before outcomes exist."""
    rows = [dict(r) for r in conn.execute("SELECT * FROM scanner_signals WHERE run_id=?", (run_id,))]
    feature = rows[0].get("feature_session") if rows else None
    if not feature:
        return
    stamp = datetime.fromisoformat(rows[0]["generated_at"].replace("Z", "+00:00"))
    stamp = stamp.replace(tzinfo=stamp.tzinfo or timezone.utc)
    target = next_session(date.fromisoformat(feature))
    now = now or datetime.now(timezone.utc)
    if not stamp <= now < datetime.combine(target, time(9), CAIRO) or feature != completed_session(stamp).isoformat():
        return
    first = conn.execute("""SELECT run_id FROM scanner_signals WHERE feature_session=?
        ORDER BY julianday(generated_at),run_id LIMIT 1""", (feature,)).fetchone()
    if first[0] != run_id:
        return
    conn.executescript(SCHEMA)
    if conn.execute("SELECT 1 FROM disclosure_study_sessions WHERE session=?", (target.isoformat(),)).fetchone():
        return
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    health = conn.execute("SELECT * FROM feed_health WHERE feed='egx_disclosures'").fetchone() if "feed_health" in tables else None
    health = dict(health) if health else {}
    checked = health.get("checked_at")
    fresh = bool(checked and health.get("status") == "partial"
                 and timedelta(0) <= stamp - datetime.fromisoformat(checked) <= timedelta(hours=6))
    snapshot = dict(version=VERSION, as_of=stamp.isoformat(), feed=health,
                    status="feed_unavailable_or_stale", eligible=0, observed_events=0, pair=None)
    if fresh and "disclosure_events" in tables and "instrument_observations" in tables:
        snapshot.update(match_pair(conn, rows, stamp))
    conn.execute("INSERT INTO disclosure_study_sessions VALUES (?,?,?)",
                 (target.isoformat(), run_id, json.dumps(snapshot, allow_nan=False)))
    conn.commit()


def match_pair(conn, rows, stamp):
    cutoff = stamp - timedelta(hours=24)
    latest = conn.execute("""SELECT * FROM (
        SELECT *, ROW_NUMBER() OVER(PARTITION BY event_id ORDER BY julianday(known_at) DESC,content_hash) AS revision
        FROM disclosure_events WHERE julianday(known_at) < julianday(?))
        WHERE revision=1 AND julianday(published_at) BETWEEN julianday(?) AND julianday(?)
        ORDER BY julianday(published_at),event_id""", (stamp.isoformat(), cutoff.isoformat(), stamp.isoformat()))
    events, blocked = {}, set()
    for event in latest:
        symbol = event["symbol"]
        if event["event_type"] != "financial_results":
            continue
        blocked.add(symbol)
        facts = json.loads(event["facts_json"])
        issuer = facts.get("issuer_evidence", {})
        periods = facts.get("stated_periods", [])
        if (symbol and event["isin"] and issuer.get("tickers") == [symbol]
                and issuer.get("isins") == [event["isin"]] and periods
                and periods[0]["scope"] == "consolidated"):
            # Several homepage categories may carry the same publication.
            events.setdefault(symbol, dict(issuer=event["isin"], event_id=event["event_id"],
                revision=event["content_hash"], source=event["source_url"], published_at=event["published_at"],
                known_at=event["known_at"], period=periods[0]))
    used = set()
    for (payload,) in conn.execute("SELECT snapshot FROM disclosure_study_sessions"):
        pair = json.loads(payload)["pair"]
        if pair:
            used.update((pair["event_symbol"], pair["control_symbol"], pair["evidence"]["issuer"]))
    eligible = {}
    for row in rows:
        symbol = row["symbol"]
        score = row.get("opportunity_score")
        if (symbol in used or score is None or not isfinite(score)
                or currency_evidence(conn, symbol, stamp) != "EGP"):
            continue
        features = eligible_features(row)
        if features is not None and isfinite(features["avg_turnover_20"]):
            eligible[symbol] = (score, features["avg_turnover_20"])
    result = dict(status="partial_no_match", eligible=len(eligible), observed_events=len(events), pair=None)
    for symbol, evidence in events.items():
        if symbol not in eligible or evidence["issuer"] in used:
            continue
        score, turnover = eligible[symbol]
        controls = [(abs(other-score), name) for name, (other, liquidity) in eligible.items()
                    if name not in blocked and abs(other-score) <= 10 and .5 <= liquidity/turnover <= 2]
        if controls:
            _, control = min(controls)
            return dict(result, status="paired", pair=dict(event_symbol=symbol, control_symbol=control,
                event_covariates=eligible[symbol], control_covariates=eligible[control], evidence=evidence))
    return result


def disclosure_study_summary(conn):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "disclosure_study_sessions" not in tables:
        return dict(version=VERSION, sessions=0, pairs=0, resolved=0, unresolved=0)
    statuses = Counter()
    eligible = observed = 0
    excess, stressed = [], []
    for session, run_id, payload in conn.execute("SELECT * FROM disclosure_study_sessions ORDER BY session"):
        snapshot = json.loads(payload)
        statuses[snapshot["status"]] += 1
        eligible += snapshot["eligible"]
        observed += snapshot["observed_events"]
        pair = snapshot["pair"]
        if not pair or "verified_outcomes" not in tables:
            continue
        returns = []
        for symbol in (pair["event_symbol"], pair["control_symbol"]):
            outcome = conn.execute("""SELECT next_day_net_return,next_day_status FROM verified_outcomes
                WHERE run_id=? AND symbol=? AND resolved_session=? AND label_version=?""",
                (run_id, symbol, session, LABEL_VERSION)).fetchone()
            if (not outcome or outcome[0] is None or not isfinite(outcome[0])
                    or outcome[1] not in ("unfilled","target","stop","horizon_exit","ambiguous_barrier_order")):
                break
            returns.append((outcome[0], outcome[0] - (.5 if outcome[1] != "unfilled" else 0)))
        if len(returns) == 2:
            excess.append(returns[0][0] - returns[1][0])
            stressed.append(returns[0][1] - returns[1][1])
    return dict(version=VERSION, sessions=sum(statuses.values()), pairs=statuses["paired"],
                resolved=len(excess), unresolved=statuses["paired"]-len(excess), coverage=dict(statuses),
                eligible_symbol_sessions=eligible, observed_issuer_sessions=observed,
                mean_excess_pct=mean(excess) if excess else None,
                stressed_excess_pct=mean(stressed) if stressed else None,
                interval_95=block_mean_interval(excess) if len(excess) >= MIN_PAIRS else None,
                minimum_pairs=MIN_PAIRS, interpretation="Exploratory association under partial coverage")
