"""Prospective candidate comparison. Production targets and orders are separate."""
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
import json
from math import isfinite, sqrt
import sqlite3
from statistics import mean, median, quantiles

from praecursor.analysis.data_quality import currency_evidence
from praecursor.analysis.paper_portfolio import load_policy
from praecursor.core.sessions import CAIRO, completed_session, is_session, next_session, session_horizon
from praecursor.data.canonical import select_candle
from praecursor.ml.rolling import block_mean_interval

VERSION = "structure-excursion-shadow-1"
SCHEMA = """CREATE TABLE IF NOT EXISTS adaptive_level_trials (
    session TEXT NOT NULL, symbol TEXT NOT NULL, horizon INTEGER NOT NULL,
    run_id INTEGER NOT NULL, plan TEXT NOT NULL, result TEXT,
    PRIMARY KEY(session,symbol,horizon));"""
HORIZONS = ((1, "next_day"), (20, "swing"))
BLOCKS = 12
INCREMENTAL_STRESS_BPS = 25  # Per side, in addition to the paper cost assumptions.


def level_plan(bars, horizon):
    """Bars are chronological [session, open, high, low, close, volume]."""
    needed = max(21, BLOCKS * horizon + 1)
    if len(bars) < needed:
        return dict(status="unavailable", reason=f"Needs {needed} contiguous completed candles")
    bars = bars[-needed:]
    if any(not all(isfinite(x) and x > 0 for x in b[1:6]) or not b[3] <= min(b[1], b[4]) <= max(b[1], b[4]) <= b[2]
           for b in bars):
        return dict(status="unavailable", reason="Invalid OHLCV in calibration window")
    dates = [date.fromisoformat(b[0]) for b in bars]
    if any(next_session(a) != b for a, b in zip(dates, dates[1:])):
        return dict(status="unavailable", reason="Missing or conflicting historical session")
    if any(abs(b[1]/a[4] - 1) > .25 or abs(b[4]/a[4] - 1) > .35 for a, b in zip(bars, bars[1:])):
        return dict(status="unavailable", reason="Historical discontinuity needs corporate-action review")
    reference = bars[-1][4]
    noise = median(max(b[2]-b[3], abs(b[2]-a[4]), abs(b[3]-a[4])) / a[4]
                   for a, b in zip(bars[-21:-1], bars[-20:]))
    recent = bars[-(5 if horizon == 1 else 20):]
    support = min(b[3] for b in recent)
    excursions = []
    for i in range(len(bars)-1-BLOCKS*horizon, len(bars)-1, horizon):
        excursions.append(max(b[2] for b in bars[i+1:i+horizon+1]) / bars[i][4] - 1)
    excursion = median(excursions)
    resistance = min((b[2] for a, b, c in zip(bars[-21:-2], bars[-20:-1], bars[-19:])
                      if b[2] > max(reference, a[2], c[2])), default=None)
    stop = support - .25 * noise * reference
    target = min(reference * (1 + excursion), resistance) if resistance else reference * (1 + excursion)
    if noise <= 0:
        return dict(status="unavailable", reason="Flat history or no positive structural risk and reward")
    if not 0 < stop < reference < target:
        return dict(status="unavailable", reason="No positive structural risk and reward", max_gap=min(noise, .05))
    return dict(status="estimated", reference=reference, stop=stop, target=target, support=support,
                noise_pct=noise*100, noise_buffer=.25*noise*reference, resistance=resistance,
                median_excursion_pct=excursion*100, excursion_samples=excursions,
                max_gap=min(noise, .05))


def economics(entry, stop, target, policy, stress=0):
    friction = (policy["spread_bps"]/2 + policy["slippage_bps_per_side"]
                + policy["impact_bps_at_limit"] + stress) / 10000
    fee = policy["fee_bps_per_side"] / 10000
    buy = (1 + friction) * (1 + fee)
    sell = (1 - friction) * (1 - fee)
    risk = entry * buy - stop * sell
    reward = target * sell - entry * buy
    max_open = (target + policy["min_reward_risk"]*stop) * sell / ((1 + policy["min_reward_risk"])*buy)
    return dict(gross_rr=(target-entry)/(entry-stop), net_rr=reward/risk,
                buy_factor=buy, sell_factor=sell, max_open_for_net_risk=max_open)


def candidate_bars(conn, symbol, feature, now):
    rows = conn.execute("""SELECT * FROM source_prices WHERE ticker=? AND date(trade_date) BETWEEN ? AND ?
                           AND julianday(collected_at) <= julianday(?)
                           ORDER BY trade_date,source""",
                        (symbol, (date.fromisoformat(feature)-timedelta(days=380)).isoformat(), feature, now.isoformat()))
    groups = {}
    for row in rows:
        groups.setdefault(row["trade_date"][:10], []).append(row)
    return [[c.session, c.open, c.high, c.low, c.close, c.volume, c.source]
            for day, group in groups.items() if is_session(date.fromisoformat(day)) and (c := select_candle(group))]


def record_adaptive_levels(conn, run_id, now=None):
    """Capture the first full dated shortlist before the existing pre-open cutoff."""
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    now = now or datetime.now(timezone.utc)
    feature = completed_session(now).isoformat()
    session = next_session(date.fromisoformat(feature))
    if now >= datetime.combine(session, time(9), CAIRO):
        return
    picks = conn.execute("""SELECT * FROM scanner_signals WHERE feature_session=?
        AND julianday(generated_at) <= julianday(?)
        AND candidate_rank BETWEEN 1 AND 5 ORDER BY julianday(generated_at),run_id,candidate_rank""",
        (feature, now.isoformat())).fetchall()
    if not picks or picks[0]["run_id"] != run_id:
        return
    picks = [r for r in picks if r["run_id"] == run_id]
    if [r["candidate_rank"] for r in picks] != list(range(1, 6)):
        return
    policy = load_policy()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for pick in picks:
        symbol = pick["symbol"]
        bars = candidate_bars(conn, symbol, feature, now)
        reference = pick["latest_close"]
        currency = currency_evidence(conn, symbol, now)
        turnover = (json.loads(pick["indicator_values_json"] or "{}").get("AvgTurnover20") or 0)
        reasons = []
        if not bars or bars[-1][0] != feature or bars[-1][4] != reference:
            reasons.append("Saved reference lacks a matching canonical completed candle")
        if currency != "EGP":
            reasons.append("EGP quote currency unverified or foreign")
        if turnover < 250000 or (pick["data_quality_score"] or 0) < 80:
            reasons.append("Liquidity or quality below existing paper floor")
        if "disclosure_events" in tables and conn.execute("""SELECT 1 FROM disclosure_events WHERE symbol=?
                AND event_type IN ('capital_action','trading_suspension')
                AND datetime(known_at) BETWEEN datetime(?) AND datetime(?)""",
                (symbol, (now-timedelta(days=7)).isoformat(), now.isoformat())).fetchone():
            reasons.append("Recent official notice needs review")
        for horizon, prefix in HORIZONS:
            sample = bars[-max(21, BLOCKS*horizon+1):]
            adaptive = level_plan(sample, horizon)
            baseline = dict(target=pick[f"{prefix}_target"], stop=pick[f"{prefix}_stop_loss"])
            for arm in (baseline, adaptive):
                target, stop = arm.get("target"), arm.get("stop")
                if (reasons or adaptive.get("max_gap") is None or not (stop and target and reference
                        and all(isfinite(x) for x in (stop, target, reference)) and 0 < stop < reference < target)):
                    arm["status"] = "unavailable"
                else:
                    arm.update(economics(reference, stop, target, policy))
                    arm["status"] = "eligible" if arm["net_rr"] >= policy["min_reward_risk"] else "cash_cost_or_risk"
            plan = dict(version=VERSION, as_of=now.isoformat(), rank=pick["candidate_rank"],
                        feature_session=feature, reference=reference, currency=currency, turnover=turnover,
                        policy=policy, max_gap=adaptive.get("max_gap"), inputs=sample, horizon_dates=session_horizon(feature, horizon),
                        reasons=reasons, baseline=baseline, adaptive=adaptive)
            conn.execute("INSERT OR IGNORE INTO adaptive_level_trials VALUES (?,?,?,?,?,NULL)",
                         (session.isoformat(), symbol, horizon, run_id, json.dumps(plan, allow_nan=False)))
    conn.commit()


def simulate(plan, arm, candles, stress=0):
    if plan[arm]["status"] != "eligible":
        return dict(status="cash", slot_pct=0, trade_pct=None, sessions=0)
    if len(candles) != len(plan["horizon_dates"]) or any(c is None for c in candles):
        return None
    reference, policy = plan["reference"], plan["policy"]
    entry = candles[0][1]
    previous = reference
    for bar in candles:
        if abs(bar[1] / previous - 1) > .25 or abs(bar[4] / previous - 1) > .35:
            return None
        previous = bar[4]
    stop, target = plan[arm]["stop"], plan[arm]["target"]
    if abs(entry/reference-1) > plan["max_gap"] or not stop < entry < target or candles[0][2] == candles[0][3]:
        return dict(status="unfilled_gap_or_lock", slot_pct=0, trade_pct=None, sessions=0)
    terms = economics(entry, stop, target, policy, stress)
    cost = entry * terms["buy_factor"]
    if terms["net_rr"] < policy["min_reward_risk"]:
        return dict(status="unfilled_net_risk", slot_pct=0, trade_pct=None, sessions=0)
    budget = min(policy["initial_equity"]*policy["max_gross_weight"]/5,
                 policy["initial_equity"]*policy["max_position_weight"],
                 plan["turnover"]*policy["max_participation"])
    # Same slot and risk budget in both arms. Daily volume provides a retrospective fill cap.
    risk = cost - stop*terms["sell_factor"]
    shares = int(min(budget/cost, policy["initial_equity"]*policy["risk_per_trade"]/risk,
                     candles[0][5]*policy["max_participation"]))
    if shares < 1:
        return dict(status="unfilled_volume", slot_pct=0, trade_pct=None, sessions=0)
    exit_price, status = candles[-1][4], "timeout"
    for held, bar in enumerate(candles, 1):
        if bar[1] <= stop:
            exit_price, status = bar[1], "gap_stop"
            break
        if bar[3] <= stop:
            exit_price, status = stop, "ambiguous_stop_first" if bar[2] >= target else "stop"
            break
        if bar[2] >= target:
            exit_price, status = target, "target"
            break
    pnl = exit_price * terms["sell_factor"] - cost
    return dict(status=status, slot_pct=100*shares*pnl/(policy["initial_equity"]/5),
                trade_pct=100*pnl/cost, sessions=held)


def resolve_adaptive_levels(conn, now=None):
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    now = now or datetime.now(timezone.utc)
    cutoff = completed_session(now).isoformat()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for row in conn.execute("SELECT * FROM adaptive_level_trials WHERE result IS NULL").fetchall():
        plan = json.loads(row["plan"])
        dates = plan["horizon_dates"]
        if dates[-1] > cutoff:
            continue
        if "corporate_actions" in tables and conn.execute(
            """SELECT 1 FROM corporate_actions WHERE symbol=? AND effective_session BETWEEN ? AND ?""",
            (row["symbol"], dates[0], dates[-1])).fetchone():
            continue
        if "disclosure_events" in tables and conn.execute("""SELECT 1 FROM disclosure_events WHERE symbol=?
            AND event_type IN ('capital_action','trading_suspension') AND datetime(known_at) <= datetime(?)
            AND date(published_at) BETWEEN ? AND ?""", (row["symbol"], now.isoformat(), dates[0], dates[-1])).fetchone():
            continue
        prices = {b[0]: b for b in candidate_bars(conn, row["symbol"], dates[-1], now)}
        candles = [prices.get(day) for day in dates]
        result = {arm: {name: simulate(plan, arm, candles, stress) for name, stress in
                       (("base", 0), ("stress", INCREMENTAL_STRESS_BPS))}
                  for arm in ("baseline", "adaptive")}
        if any(value is None for arm in result.values() for value in arm.values()):
            continue
        conn.execute("UPDATE adaptive_level_trials SET result=? WHERE session=? AND symbol=? AND horizon=?",
                     (json.dumps(result, allow_nan=False), row["session"], row["symbol"], row["horizon"]))
    conn.commit()
    return adaptive_summary(conn)


def adaptive_summary(conn):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='adaptive_level_trials'").fetchone():
        return {"version": VERSION, "horizons": []}
    reports = []
    for horizon, _ in HORIZONS:
        sessions = {}
        for session, plan, result in conn.execute(
            "SELECT session,plan,result FROM adaptive_level_trials WHERE horizon=? ORDER BY session, symbol", (horizon,)):
            sessions.setdefault(session, []).append((json.loads(plan), json.loads(result) if result else None))
        complete = [[r for _, r in rows] for rows in sessions.values()
                    if len(rows) == 5 and all(result is not None for _, result in rows)]
        report = dict(horizon=horizon, recorded_sessions=len(sessions), paired_sessions=len(complete),
                      awaiting_resolution=len(sessions)-len(complete), promotion="shadow only")
        for arm in ("baseline", "adaptive"):
            daily = [mean(r[arm]["base"]["slot_pct"] for r in rows) for rows in complete]
            stress = [mean(r[arm]["stress"]["slot_pct"] for r in rows) for rows in complete]
            slots = [r[arm]["base"] for rows in complete for r in rows]
            filled = [r for r in slots if r["trade_pct"] is not None]
            returns = [r["trade_pct"] for r in filled]
            # Swing cohorts overlap. A daily sequence of independent portfolios would overstate exposure.
            equity, peak, drawdown = 100, 100, 0
            for change in daily if horizon == 1 else ():
                equity *= 1 + change / 100
                peak = max(peak, equity)
                drawdown = max(drawdown, (1-equity/peak)*100)
            report[arm] = dict(paired_slots=len(slots), filled=len(filled),
                eligible=sum(p[arm]["status"] == "eligible" for rows in sessions.values() for p, _ in rows),
                plan_statuses=dict(Counter(p[arm]["status"] for rows in sessions.values() for p, _ in rows)),
                statuses=dict(Counter(r["status"] for r in slots)),
                mean_net_trade_pct=mean(returns) if returns else None,
                payoff_quartiles_pct=quantiles(returns, n=4, method="inclusive") if len(returns) >= 4 else None,
                mean_candidate_pct=mean(daily) if daily else None, stress_candidate_pct=mean(stress) if stress else None,
                mean_holding_sessions=mean(r["sessions"] for r in filled) if filled else None,
                max_drawdown_pct=drawdown if daily and horizon == 1 else None)
        delta = [mean(r["adaptive"]["base"]["slot_pct"]-r["baseline"]["base"]["slot_pct"] for r in rows)
                 for rows in complete]
        report["paired_excess_95pct_interval"] = (
            block_mean_interval(delta, block=max(5, horizon)) if len(delta) >= max(20, 3*horizon) else None)
        reports.append(report)
    return dict(version=VERSION, horizons=reports)


def adaptive_notes(conn, run_id):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='adaptive_level_trials'").fetchone():
        return {}
    notes = {}
    for symbol, horizon, payload in conn.execute(
        "SELECT symbol,horizon,plan FROM adaptive_level_trials WHERE run_id=? ORDER BY horizon", (run_id,)):
        plan = json.loads(payload)
        arm = plan["adaptive"]
        prefix = f"Shadow · {horizon} session{'s' if horizon != 1 else ''}"
        if arm["status"] == "unavailable":
            reason = "; ".join(plan["reasons"]) or arm.get("reason") or "Insufficient comparable evidence"
            text = f"{prefix} · {reason}"
        else:
            precision = 4 if plan["reference"] < 1 else 3
            def amount(value):
                return f"{value:.{precision}f}"
            text = (f"{prefix} · target {amount(arm['target'])}, stop {amount(arm['stop'])}, "
                    f"net reward/risk {arm['net_rr']:.2f}× at the {amount(plan['reference'])} reference close. "
                    f"Stop below support {amount(arm['support'])} by {amount(arm['noise_buffer'])}. "
                    f"Median favorable move {arm['median_excursion_pct']:.1f}%"
                    + (f", capped at resistance {amount(arm['resistance'])}." if arm["resistance"] else ".")
                    + (" Cash at reference under cost/risk gate." if arm["status"] == "cash_cost_or_risk" else
                       f" Max opening price {amount(min(plan['reference']*(1+plan['max_gap']), arm['max_open_for_net_risk']))}."))
        notes.setdefault(symbol, []).append(text)
    return notes
