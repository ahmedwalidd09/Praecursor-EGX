"""Frozen published-signal evidence, paired baselines and public-data limitations."""
from collections import defaultdict
from datetime import datetime, timezone, timedelta
import json
import sqlite3

from praecursor.core.sessions import completed_session
from praecursor.data.canonical import select_candle
from praecursor.ml.rolling import block_mean_interval


def frozen_evidence(frame):
    daily = []
    for session, universe in frame.groupby("session"):
        selected = universe[universe.candidate_rank.between(1,5)]
        if selected.empty or universe.next_day_net_return_pct.isna().any() or universe.next_day_target_hit.isna().any():
            continue
        mean = float(selected.next_day_net_return_pct.mean())
        baseline = float(universe.next_day_net_return_pct.mean())
        filled_fraction = float((selected.next_day_status != "unfilled").mean())
        daily.append(dict(session=str(session), selections=len(selected), mean_net_return_pct=mean,
                          universe_mean_net_return_pct=baseline, excess_pct=mean-baseline,
                          stressed_net_return_pct=mean-.5*filled_fraction))
    interval = block_mean_interval([r["excess_pct"] for r in daily])
    average = lambda key: sum(r[key] for r in daily)/len(daily) if daily else None
    return dict(sessions=len(daily), selections=sum(r["selections"] for r in daily),
                mean_net_return_pct=average("mean_net_return_pct"),
                universe_mean_net_return_pct=average("universe_mean_net_return_pct"),
                stressed_net_return_pct=average("stressed_net_return_pct"),
                excess_95pct_interval=interval, daily=daily,
                status="Evidence accumulating" if len(daily)<60 or interval is None else
                       "Positive measured excess in this sample" if interval[0]>0 else "No demonstrated excess",
                basis="Frozen daily shortlist versus equal-weight eligible published universe; not EGX30, not portfolio P&L",
                cost_scenario="25 bps existing round-trip label scenario; stress adds 50 bps per filled trade",
                limitations="Only complete sessions; surviving configured universe; repeated research trials require prospective confirmation")


def data_health(conn):
    session=completed_session().isoformat()
    rows=conn.execute("SELECT * FROM source_prices WHERE date(trade_date)=?",(session,)).fetchall()
    groups=defaultdict(list)
    for row in rows:
        groups[row["ticker"]].append(row)
    candles=[select_candle(group) for group in groups.values()]
    tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return dict(expected_session=session,observed_symbols=len(groups),
                canonical_symbols=sum(c is not None for c in candles),
                conflicting_or_invalid_symbols=sum(c is None for c in candles),
                single_source_symbols=sum(c is not None and c.agreeing_sources==1 for c in candles),
                source_coverage={r["source"]:r["n"] for r in conn.execute("SELECT source,count(DISTINCT ticker) AS n FROM source_prices WHERE date(trade_date)=? GROUP BY source",(session,))},
                revision_journal="Recording new observations" if "price_observations" in tables else "Not started",
                intraday_execution="Unverified: daily scenarios only", order_book="No connected order-book feed",
                corporate_actions="Verified adjustment records supported; new disclosures require effective-date/factor review",
                calendar="Weekdays plus configured closure overrides; official holiday feed not connected",
                historical_universe="Saved scan universes from collection onward; full delisted-security archive unavailable")


def event_cohorts(conn, frame):
    tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "disclosure_events" not in tables:
        return []
    cohorts=defaultdict(list)
    picks=frame[frame.candidate_rank.between(1,5) & frame.next_day_net_return_pct.notna()]
    for row in picks.itertuples():
        signal=conn.execute("SELECT generated_at FROM scanner_signals WHERE symbol=? AND feature_session=? ORDER BY generated_at LIMIT 1",(row.symbol,row.session)).fetchone()
        if not signal:
            continue
        stamp=datetime.fromisoformat(signal[0].replace("Z","+00:00"))
        kinds=conn.execute("""SELECT DISTINCT event_type FROM disclosure_events WHERE symbol=?
             AND datetime(known_at)<=datetime(?) AND datetime(known_at)>=datetime(?)""",
             (row.symbol,stamp.isoformat(),(stamp-timedelta(days=7)).isoformat())).fetchall()
        for kind in kinds:
            cohorts[kind[0]].append((row.session,row.next_day_net_return_pct))
    return [dict(event_type=kind,selections=len(rows),sessions=len({r[0] for r in rows}),
                 mean_net_return_pct=sum(r[1] for r in rows)/len(rows),status="Exploratory association; not a causal or validated ranking signal")
            for kind,rows in sorted(cohorts.items())]


def save_research(conn, frame):
    conn.row_factory=sqlite3.Row
    conn.execute("CREATE TABLE IF NOT EXISTS research_snapshots (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)")
    report=dict(updated_at=datetime.now(timezone.utc).isoformat(),performance=frozen_evidence(frame),
                data_health=data_health(conn),event_cohorts=event_cohorts(conn,frame))
    conn.execute("INSERT OR REPLACE INTO research_snapshots VALUES (1,?)",(json.dumps(report,allow_nan=False),))
    conn.commit()
    return report


def research_summary(conn):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='research_snapshots'").fetchone():
        return {}
    row=conn.execute("SELECT payload FROM research_snapshots WHERE id=1").fetchone()
    return json.loads(row[0]) if row else {}
