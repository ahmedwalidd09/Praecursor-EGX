"""Weekly frozen top-five evaluation; target touches never imply trade profitability."""
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json

from praecursor.analysis.outcomes import outcome_category, LABEL_VERSION
from praecursor.analysis.research import frozen_evidence
from praecursor.analysis.paper_portfolio import paper_summary
from praecursor.core.sessions import CAIRO, PUBLICATION_CUTOFF

SCHEMA = """CREATE TABLE IF NOT EXISTS weekly_reports (
 week_end TEXT PRIMARY KEY, created_at TEXT, protocol_hash TEXT, payload TEXT,
 delivery_status TEXT NOT NULL DEFAULT 'pending');"""
PROTOCOL = dict(version="weekly-2", label_version=LABEL_VERSION, shortlist=5,
    cost_bps=25, stress_additional_bps=50, baseline="matched eligible published universe",
    aggregation="five eligible picks and complete matched-universe outcomes; mean selection return, not portfolio return",
    unresolved="excluded from paired performance, always counted separately")


def completed_week(now=None):
    local = (now or datetime.now(timezone.utc)).astimezone(CAIRO)
    today = local.date()
    if local.time() < PUBLICATION_CUTOFF:
        today -= timedelta(days=1)
    return today-timedelta(days=(today.weekday()-3)%7)


def build_weekly(conn, frame, end, now=None):
    now = now or datetime.now(timezone.utc)
    start = end-timedelta(days=4)
    week = frame[frame.session.between(start.isoformat(),end.isoformat())]
    picks = week[week.candidate_rank.between(1,5)].sort_values(["session", "candidate_rank"])
    categories = Counter(outcome_category(r.next_day_status,r.next_day_net_return_pct) for r in picks.itertuples())
    rows = [dict(symbol=r.symbol, session=r.session, rank=int(r.candidate_rank),
        target="hit" if r.next_day_target_hit==1 else "miss" if r.next_day_target_hit==0 else "unresolved",
        trade=outcome_category(r.next_day_status,r.next_day_net_return_pct), status=r.next_day_status,
        net_return_pct=float(r.next_day_net_return_pct) if r.next_day_net_return_pct==r.next_day_net_return_pct and r.next_day_net_return_pct is not None else None)
        for r in picks.itertuples()]
    paper = paper_summary(conn)
    curve = [d for d in paper["curve"] if start.isoformat()<=d["session"]<=end.isoformat()]
    audit = conn.execute("SELECT payload FROM quality_audits ORDER BY checked_at DESC LIMIT 1").fetchone()
    quality = json.loads(audit[0]) if audit else {}
    experiments = []
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='shadow_experiments'").fetchone():
        experiments = [dict(name=r["name"],status=r["status"],
            resolved_sessions=conn.execute("SELECT count(*) FROM shadow_sessions WHERE name=? AND result IS NOT NULL",(r["name"],)).fetchone()[0])
            for r in conn.execute("SELECT name,status FROM shadow_experiments ORDER BY registered_at")]
    return dict(week_start=start.isoformat(),week_end=end.isoformat(),created_at=now.isoformat(),
        protocol=PROTOCOL, predictions=len(rows), sessions=int(picks.session.nunique()),
        target_hits=sum(r["target"]=="hit" for r in rows),target_misses=sum(r["target"]=="miss" for r in rows),
        categories={key:categories[key] for key in ("profitable","loss","breakeven","not_filled","ambiguous","unresolved")},
        performance=frozen_evidence(week), cumulative_evidence=frozen_evidence(frame),
        paper=dict(weekly_pnl_egp=sum(d["pnl"] for d in curve),resolved_weekly_sessions=len(curve),
                   equity=paper["equity"],max_drawdown_pct=paper["max_drawdown_pct"],
                   pending_sessions=paper.get("pending_sessions",0),basis="Hypothetical daily-bar fills; cumulative drawdown"),
        data_quality={key:quality.get(key) for key in ("checked_at","expected_session","coverage_pct","market_wide_data_gap","stale_or_missing","conflicting_or_invalid","unknown_or_conflicting_currency","review_queue","calendar_status")},
        predictions_detail=rows, experiments=experiments,
        definitions="Hit/miss = target touched/not touched. Trade profit is net of assumed costs. Ambiguous barrier order is separate; its return is a conservative stop-first scenario. Unfilled is cash; unresolved is not a loss.")


def freeze_weekly(conn, frame, end, now=None):
    conn.executescript(SCHEMA)
    existing = conn.execute("SELECT payload FROM weekly_reports WHERE week_end=?",(end.isoformat(),)).fetchone()
    if existing:
        return json.loads(existing[0])
    report = build_weekly(conn,frame,end,now)
    digest = hashlib.sha256(json.dumps(PROTOCOL,sort_keys=True).encode()).hexdigest()[:16]
    report["protocol_hash"] = digest
    conn.execute("INSERT INTO weekly_reports(week_end,created_at,protocol_hash,payload) VALUES (?,?,?,?)",
                 (end.isoformat(),report["created_at"],digest,json.dumps(report,allow_nan=False)))
    conn.commit()
    return report


def format_weekly(report):
    def pct(value):
        return "unavailable" if value is None else f"{value:+.2f}%"
    perf, cat, paper, quality = (report[k] for k in ("performance","categories","paper","data_quality"))
    interval = report["cumulative_evidence"]["excess_95pct_interval"]
    uncertainty = f"{pct(interval[0])} to {pct(interval[1])}" if interval else "insufficient sessions for an interval"
    lines = [f"Praecursor weekly review | {report['week_start']} to {report['week_end']}",
        f"Original top five: {report['predictions']} predictions across {report['sessions']} sessions.",
        f"Target touches: {report['target_hits']} hits / {report['target_misses']} misses.",
        "Trade scenarios: " + ", ".join(f"{n} {key.replace('_',' ')}" for key,n in cat.items())+".",
        f"Paired complete sessions: {perf['sessions']}. Mean net selection return: {pct(perf['mean_net_return_pct'])}.",
        f"Matched universe: {pct(perf['universe_mean_net_return_pct'])}; higher-cost selections: {pct(perf['stressed_net_return_pct'])}.",
        f"Cumulative excess 95% interval: {uncertainty}.",
        f"Paper P&L this week: EGP {paper['weekly_pnl_egp']:.2f}; lifetime drawdown: {pct(paper['max_drawdown_pct'])}; pending sessions: {paper['pending_sessions']}.",
        f"Latest data audit ({quality.get('expected_session')}): {quality.get('coverage_pct',0) or 0:.1f}% current; {len(quality.get('stale_or_missing') or [])} stale/missing; {len(quality.get('conflicting_or_invalid') or [])} invalid/conflicting; {len(quality.get('unknown_or_conflicting_currency') or [])} currency gaps.",
        report["definitions"],
        "Benchmark is the eligible published universe, not EGX30. Public holiday/corporate-action coverage is incomplete; uncertainty remains flagged.",
        f"Frozen evaluation protocol: {report.get('protocol_hash','preview')}. No actual trades."]
    for experiment in report.get("experiments",[]):
        lines.append(f"Trial {experiment['name']}: {experiment['status']}; {experiment['resolved_sessions']}/60 resolved sessions.")
    return "\n\n".join(lines)
