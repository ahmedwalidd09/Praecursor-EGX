"""Prospective, immutable paper plans and conservative daily-bar execution scenarios.

This ledger never places orders and never represents simulated fills as observations.
"""
from collections import defaultdict
from datetime import date, datetime, time, timezone, timedelta
import hashlib
import json
from math import floor, isfinite, sqrt
from pathlib import Path
import sqlite3
from statistics import correlation

from praecursor.core.sessions import CAIRO, completed_session, next_session
from praecursor.data.canonical import select_candle

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = """
CREATE TABLE IF NOT EXISTS paper_sessions (
 session TEXT PRIMARY KEY, run_id INTEGER NOT NULL, created_at TEXT NOT NULL,
 policy_hash TEXT NOT NULL, policy_json TEXT NOT NULL, equity_before REAL NOT NULL,
 state TEXT NOT NULL, reason TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS paper_orders (
 session TEXT NOT NULL, symbol TEXT NOT NULL, candidate_rank INTEGER NOT NULL,
 sector TEXT NOT NULL, quantity INTEGER NOT NULL, reference REAL NOT NULL,
 target REAL NOT NULL, stop REAL NOT NULL, avg_turnover REAL NOT NULL,
 decision TEXT NOT NULL, reasons_json TEXT NOT NULL, outcome_json TEXT,
 PRIMARY KEY(session,symbol));
"""


def load_policy(path=None):
    policy = json.loads(Path(path or ROOT / "config/paper_policy.json").read_text())
    if not isinstance(policy.get("version"), str) or not policy["version"]:
        raise ValueError("Paper policy needs a version")
    for key, value in policy.items():
        if key == "version":
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value <= 0:
            raise ValueError(f"Invalid paper policy: {key}")
    for key in ("risk_per_trade", "max_position_weight", "max_sector_weight", "max_gross_weight",
                "max_participation", "max_pair_correlation", "max_drawdown"):
        if policy[key] > 1:
            raise ValueError(f"Invalid fraction: {key}")
    if not policy["max_position_weight"] <= policy["max_sector_weight"] <= policy["max_gross_weight"]:
        raise ValueError("Position/sector/gross limits must be ordered")
    return policy


def execution_scenario(order, bar, policy):
    """Daily volume caps are retrospective fill bounds, not opening auction liquidity."""
    reference, target, stop = (float(order[k]) for k in ("reference", "target", "stop"))
    result = dict(status="unfilled", quantity=0, pnl=0.0, net_return_pct=None,
                  target_touched=bool(bar.high >= target), ambiguous=False,
                  fill_basis="Daily OHLCV scenario; spread, slippage and queue fills unobserved")
    if abs(bar.open / reference - 1) > .25:
        return dict(result, status="corporate_action_review", pnl=None)
    if not stop < bar.open < target or bar.low == bar.high:
        return result
    quantity = min(int(order["quantity"]), floor(bar.volume * policy["max_participation"]))
    if quantity <= 0:
        return result
    participation = quantity * bar.open / max(order["avg_turnover"], 1)
    impact = policy["impact_bps_at_limit"] * sqrt(participation / policy["max_participation"])
    friction = (policy["spread_bps"] / 2 + policy["slippage_bps_per_side"] + impact) / 10000
    entry = bar.open * (1 + friction)
    if entry >= target:
        return result
    # Keep the opening gap from increasing the amount committed above the saved plan.
    fee = policy["fee_bps_per_side"] / 10000
    quantity = min(quantity, floor(order["quantity"] * reference / (entry * (1 + fee))))
    original_risk = order["quantity"] * (reference - stop + reference * 2 * (friction + fee))
    opening_risk = entry * (1 + fee) - stop * (1 - friction) * (1 - fee)
    quantity = min(quantity, floor(original_risk / opening_risk))
    if quantity <= 0:
        return result
    ambiguous = bar.low <= stop and bar.high >= target
    exit_level = stop if bar.low <= stop else target if bar.high >= target else bar.close
    exit_price = exit_level * (1 - friction)
    pnl = quantity * (exit_price * (1 - fee) - entry * (1 + fee))
    status = "ambiguous_stop_first" if ambiguous else "stop" if bar.low <= stop else "target" if bar.high >= target else "close"
    return dict(result, status=status, quantity=quantity, partial=quantity < order["quantity"],
                entry=entry, exit=exit_price, pnl=pnl, net_return_pct=pnl / (quantity * entry) * 100,
                ambiguous=ambiguous, round_trip_friction_bps=2 * (friction + fee) * 10000)


def paper_summary(conn):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    empty = dict(status="Awaiting first prospective plan", sessions=0, trades=0, equity=None,
                 net_return_pct=None, max_drawdown_pct=None, expectancy_egp=None, orders=[], curve=[])
    if "paper_sessions" not in tables:
        return empty
    sessions = [dict(r) for r in conn.execute("SELECT * FROM paper_sessions ORDER BY session")]
    if not sessions:
        return empty
    initial = json.loads(sessions[0]["policy_json"])["initial_equity"]
    equity = peak = initial
    drawdown, trades, wins, pnls, curve, pending = 0, 0, 0, [], [], 0
    for session in sessions:
        outcomes = [json.loads(r[0]) for r in conn.execute(
            "SELECT outcome_json FROM paper_orders WHERE session=? AND outcome_json IS NOT NULL", (session["session"],))]
        if session["state"] != "resolved":
            pending += 1
            continue
        day_pnl = sum(o.get("pnl") or 0 for o in outcomes)
        equity += day_pnl
        peak = max(peak, equity)
        drawdown = max(drawdown, 1 - equity / peak)
        filled = [o for o in outcomes if o.get("quantity", 0) > 0]
        trades += len(filled)
        wins += sum(o["pnl"] > 0 for o in filled)
        pnls.extend(o["pnl"] for o in filled)
        curve.append(dict(session=session["session"], equity=equity, pnl=day_pnl, trades=len(filled)))
    latest = sessions[-1]
    orders = [dict(r) for r in conn.execute("SELECT * FROM paper_orders WHERE session=? ORDER BY candidate_rank", (latest["session"],))]
    for order in orders:
        order["reasons"] = json.loads(order.pop("reasons_json"))
        order["outcome"] = json.loads(order.pop("outcome_json") or "null")
    return dict(empty, status=latest["reason"] or latest["state"], session=latest["session"],
                sessions=len(curve), pending_sessions=pending, trades=trades, equity=equity,
                net_return_pct=(equity / initial - 1) * 100, max_drawdown_pct=drawdown * 100,
                expectancy_egp=sum(pnls) / trades if trades else None,
                win_rate=wins / trades if trades else None, orders=orders, curve=curve,
                policy=json.loads(latest["policy_json"]), policy_hash=latest["policy_hash"],
                basis="Prospective paper scenarios only; no actual fills or broker positions")


def _returns(conn, symbol, cutoff):
    groups = defaultdict(list)
    for row in conn.execute("SELECT * FROM source_prices WHERE ticker=? AND date(trade_date)<=? ORDER BY trade_date DESC LIMIT 250", (symbol, cutoff)):
        groups[str(row["trade_date"])[:10]].append(row)
    bars = [select_candle(groups[d]) for d in sorted(groups)]
    return {b.session: b.close / a.close - 1 for a, b in zip(bars, bars[1:]) if a and b}


def record_plan(conn, run_id, now=None, policy=None, sectors=None):
    """Freeze the first pre-open shortlist and risk decisions; never backfill a live record."""
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    policy = policy or load_policy()
    now = now or datetime.now(timezone.utc)
    picks = [dict(r) for r in conn.execute("SELECT * FROM scanner_signals WHERE run_id=? AND candidate_rank BETWEEN 1 AND 5 ORDER BY candidate_rank", (run_id,))]
    if not picks or not picks[0].get("feature_session"):
        return False
    feature = picks[0]["feature_session"]
    target_session = next_session(date.fromisoformat(feature))
    deadline = datetime.combine(target_session, time(9), CAIRO)
    if now >= deadline or feature != completed_session(now).isoformat():
        return False
    if conn.execute("SELECT 1 FROM paper_sessions WHERE session=?", (target_session.isoformat(),)).fetchone():
        return False
    summary = paper_summary(conn)
    equity = summary["equity"] if summary["equity"] is not None else policy["initial_equity"]
    reason = ""
    if summary.get("pending_sessions", 0):
        reason = "Paused: prior paper positions remain unresolved"
    elif (summary["max_drawdown_pct"] or 0) >= policy["max_drawdown"] * 100:
        reason = "Paused: drawdown limit reached; policy review required"
    recent = summary["curve"][-int(policy["drift_window_sessions"]):]
    if sum(d["trades"] for d in recent) >= policy["min_drift_trades"] and sum(d["pnl"] for d in recent) < 0:
        reason = "Paused: recent paper expectancy is negative; policy review required"
    payload = json.dumps(policy, sort_keys=True)
    conn.execute("INSERT INTO paper_sessions VALUES (?,?,?,?,?,?,?,?)", (target_session.isoformat(), run_id,
                 now.isoformat(), hashlib.sha256(payload.encode()).hexdigest()[:16], payload, equity, "planned", reason))
    sectors = sectors or {}
    gross, sector_value, accepted_returns = 0, defaultdict(float), []
    for pick in picks:
        reference, target, stop = (float(pick.get(k) or 0) for k in ("latest_close", "next_day_target", "next_day_stop_loss"))
        values = json.loads(pick.get("indicator_values_json") or "{}")
        turnover = float(values.get("AvgTurnover20") or 0)
        sector = sectors.get(pick["symbol"], "Unknown") or "Unknown"
        reasons = [reason] if reason else []
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        currency = None
        if "instrument_observations" in tables:
            observation = conn.execute("""SELECT currency FROM instrument_observations WHERE ticker=?
                AND datetime(observed_at)<=datetime(?) AND datetime(observed_at)>=datetime(?)
                ORDER BY observed_at DESC LIMIT 1""", (pick["symbol"], now.isoformat(), (now-timedelta(days=7)).isoformat())).fetchone()
            currency = observation[0] if observation else None
        if currency != "EGP":
            reasons.append("Paper book requires a recently observed EGP quote currency; foreign or unknown currency excluded")
        if "disclosure_events" in tables:
            events = conn.execute("""SELECT DISTINCT event_type FROM disclosure_events WHERE symbol=?
                AND event_type IN ('capital_action','trading_suspension')
                AND datetime(known_at)<=datetime(?) AND datetime(known_at)>=datetime(?)""",
                (pick["symbol"],now.isoformat(),(now-timedelta(days=7)).isoformat())).fetchall()
            if events:
                reasons.append("Recent official capital-action or suspension disclosure requires review")
        quantity = 0
        if not all(isfinite(v) for v in (reference, target, stop, turnover)) or not 0 < stop < reference < target:
            reasons.append("Invalid published levels")
        elif (target - reference) / (reference - stop) < policy["min_reward_risk"]:
            reasons.append("Reward/risk below policy minimum")
        if turnover < 250000 or (pick.get("data_quality_score") or 0) < 80:
            reasons.append("Insufficient liquidity or price quality")
        returns = _returns(conn, pick["symbol"], feature)
        if len(returns) < 20:
            reasons.append("Insufficient aligned history for correlation control")
        for other in accepted_returns:
            days = sorted(set(returns) & set(other))[-60:]
            if len(days) < 20:
                reasons.append("Insufficient common sessions for correlation control")
                break
            try:
                rho = correlation([returns[d] for d in days], [other[d] for d in days])
            except Exception:
                reasons.append("Correlation unavailable")
                break
            if rho >= policy["max_pair_correlation"]:
                reasons.append("Highly correlated with an earlier paper selection")
                break
        if not reasons:
            cost = (2 * policy["fee_bps_per_side"] + policy["spread_bps"] + 2 * policy["slippage_bps_per_side"] + 2 * policy["impact_bps_at_limit"]) / 10000
            if (target - reference) / reference <= 2 * cost:
                reasons.append("Target room insufficient after stressed costs")
            budget = min(equity * policy["max_position_weight"], equity * policy["max_gross_weight"] - gross,
                         equity * policy["max_sector_weight"] - sector_value[sector], turnover * policy["max_participation"])
            quantity = max(0, floor(min(budget / reference, equity * policy["risk_per_trade"] / (reference - stop + reference * cost))))
            if not quantity:
                reasons.append("Position, sector, cash or participation limit exhausted")
        if reasons:
            quantity = 0
        else:
            gross += quantity * reference
            sector_value[sector] += quantity * reference
            accepted_returns.append(returns)
        conn.execute("INSERT INTO paper_orders VALUES (?,?,?,?,?,?,?,?,?,?,?,NULL)", (target_session.isoformat(), pick["symbol"],
                     pick["candidate_rank"], sector, quantity, reference, target, stop, turnover,
                     "paper_eligible" if quantity else "watch_only", json.dumps(reasons or ["Passed paper risk checks; execution remains hypothetical"])))
    conn.commit()
    return True


def resolve_paper(conn, cutoff=None):
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    cutoff = min(cutoff or completed_session().isoformat(), completed_session().isoformat())
    for session in conn.execute("SELECT * FROM paper_sessions WHERE state!='resolved' AND session<=? ORDER BY session", (cutoff,)).fetchall():
        policy = json.loads(session["policy_json"])
        unresolved = False
        for row in conn.execute("SELECT * FROM paper_orders WHERE session=? AND outcome_json IS NULL", (session["session"],)).fetchall():
            order = dict(row)
            if not order["quantity"]:
                outcome = dict(status="watch_only", quantity=0, pnl=0)
            else:
                bar = select_candle(conn.execute("SELECT * FROM source_prices WHERE ticker=? AND date(trade_date)=?", (order["symbol"], order["session"])).fetchall())
                if not bar:
                    unresolved = True
                    continue
                outcome = execution_scenario(order, bar, policy)
                if outcome["pnl"] is None:
                    unresolved = True
                    continue
            conn.execute("UPDATE paper_orders SET outcome_json=? WHERE session=? AND symbol=?", (json.dumps(outcome), order["session"], order["symbol"]))
        if not unresolved:
            conn.execute("UPDATE paper_sessions SET state='resolved' WHERE session=?", (session["session"],))
    conn.commit()
